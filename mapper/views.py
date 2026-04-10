import json
from datetime import datetime

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .models import Project, Task, Link
from .groq_client import generate_chain, analyze_delay_optimization


# ──────────────────────────────────────────────
# TEMPLATE VIEW
# ──────────────────────────────────────────────

def dashboard(request):
    """Serve the main SPA-like dashboard template."""
    return render(request, 'mapper/index.html')

def login_page_view(request):
    """Serve the dedicated login page template. Redirect if already logged in."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'mapper/login.html')

def register_page_view(request):
    """Serve the dedicated registration page template. Redirect if already logged in."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'mapper/register.html')


# ──────────────────────────────────────────────
# HELPER: Get or create default project
# ──────────────────────────────────────────────

def _get_project(request):
    """Get the user's project, or create one."""
    user = request.user if request.user.is_authenticated else None
    
    if user:
        project = Project.objects.filter(owner=user).first()
    else:
        project = Project.objects.filter(owner__isnull=True).first()

    if not project:
        project_name = f"{user.username}'s Project" if user else "Default Project"
        project = Project.objects.create(name=project_name, owner=user)
    return project


def _serialize_project(project):
    tasks = list(project.tasks.all().values('task_id', 'name', 'duration', 'delay', 'timestamp'))
    links = list(project.links.all().values('source_task_id', 'target_task_id'))

    nodes = [{"id": t["task_id"], "name": t["name"], "duration": t["duration"], 
              "delay": t["delay"], "timestamp": t["timestamp"]} for t in tasks]
    link_list = [{"source": l["source_task_id"], "target": l["target_task_id"]} for l in links]

    return {"nodes": nodes, "links": link_list, "project_name": project.name}


# ──────────────────────────────────────────────
# API: PROJECT DATA
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
def get_project(request):
    project = _get_project(request)
    return JsonResponse(_serialize_project(project))


# ──────────────────────────────────────────────
# API: TASK CRUD
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def create_task(request):
    try:
        data = json.loads(request.body)
        project = _get_project(request)

        task_id = data.get("task_id", str(int(datetime.now().timestamp() * 1000)))
        name = data.get("name", "Untitled Task")
        duration = int(data.get("duration", 10))
        timestamp = data.get("timestamp", datetime.now().strftime("%I:%M %p"))

        task = Task.objects.create(
            project=project,
            task_id=task_id,
            name=name,
            duration=duration,
            delay=0,
            timestamp=timestamp,
        )

        return JsonResponse({
            "status": "created",
            "task": {"id": task.task_id, "name": task.name, "duration": task.duration,
                     "delay": task.delay, "timestamp": task.timestamp}
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    project = _get_project(request)
    Task.objects.filter(project=project, task_id=task_id).delete()
    Link.objects.filter(project=project, source_task_id=task_id).delete()
    Link.objects.filter(project=project, target_task_id=task_id).delete()
    return JsonResponse({"status": "deleted", "task_id": task_id})


# ──────────────────────────────────────────────
# API: DELAY PROPAGATION
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def propagate_delay(request):
    try:
        data = json.loads(request.body)
        target_id = data.get("target_id")
        days = int(data.get("days", 0))
        project = _get_project(request)

        target_task = Task.objects.filter(project=project, task_id=target_id).first()
        if not target_task:
            return JsonResponse({"error": "Task not found"}, status=404)

        target_task.delay = days
        target_task.save()

        # Propagate downstream
        downstream_links = Link.objects.filter(project=project, source_task_id=target_id)
        for link in downstream_links:
            downstream = Task.objects.filter(project=project, task_id=link.target_task_id).first()
            if downstream:
                downstream.delay = max(downstream.delay, days - 2)
                downstream.save()

        return JsonResponse(_serialize_project(project))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ──────────────────────────────────────────────
# API: AI — CHAIN GENERATION (Groq)
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def generate_chain_view(request):
    try:
        data = json.loads(request.body)
        prompt = data.get("prompt", "")
        if not prompt:
            return JsonResponse({"error": "Prompt is required"}, status=400)

        result = generate_chain(prompt)
        if result is None:
            return JsonResponse({"error": "AI service unavailable. Check your GROQ_API_KEY in .env"}, status=503)

        # Save generated chain to DB
        project = _get_project(request)
        # Clear old data
        project.tasks.all().delete()
        project.links.all().delete()

        now = datetime.now()
        for node in result.get("nodes", []):
            Task.objects.create(
                project=project,
                task_id=node["id"],
                name=node["name"],
                duration=node.get("duration", 10),
                delay=node.get("delay", 0),
                timestamp=now.strftime("%I:%M %p"),
            )

        for link in result.get("links", []):
            Link.objects.create(
                project=project,
                source_task_id=link["source"],
                target_task_id=link["target"],
            )

        return JsonResponse(_serialize_project(project))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ──────────────────────────────────────────────
# API: AI — DELAY OPTIMIZATION ANALYSIS (Groq)
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def analyze_delay_view(request):
    try:
        project = _get_project(request)
        project_data = _serialize_project(project)

        analysis = analyze_delay_optimization(project_data)
        if analysis is None:
            return JsonResponse({"error": "AI service unavailable. Check your GROQ_API_KEY in .env"}, status=503)

        return JsonResponse({"analysis": analysis})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ──────────────────────────────────────────────
# API: PDF EXPORT
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def export_pdf(request):
    project = _get_project(request)
    tasks = project.tasks.all()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="DelayChain-Report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    elements = []

    # Title
    title_style = ParagraphStyle('Title', fontSize=22, spaceAfter=20,
                                  textColor=HexColor('#c5a37d'), fontName='Helvetica-Bold')
    elements.append(Paragraph("Delay Chain Analysis Report", title_style))
    elements.append(Spacer(1, 10))

    subtitle_style = ParagraphStyle('Sub', fontSize=10, spaceAfter=30, textColor=HexColor('#8b949e'))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Project: {project.name}", subtitle_style))

    # Table
    table_data = [["Timestamp", "Task", "Duration", "Delay", "Status"]]
    for t in tasks:
        status = "CRITICAL DELAY" if t.delay > 0 else "ON TRACK"
        table_data.append([t.timestamp, t.name, f"{t.duration}d", f"{t.delay}d", status])

    table = Table(table_data, colWidths=[3*cm, 5*cm, 2.5*cm, 2.5*cm, 3.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#161b22')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#c5a37d')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), HexColor('#f0f6fc')),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#0a0c10')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#30363d')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#0a0c10'), HexColor('#161b22')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(table)

    doc.build(elements)
    return response


# ──────────────────────────────────────────────
# API: SAVE FULL PROJECT (bulk update)
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def save_project(request):
    """Bulk save/overwrite project data from frontend state."""
    try:
        data = json.loads(request.body)
        project = _get_project(request)

        nodes = data.get("nodes", [])
        links = data.get("links", [])

        # Clear and re-create
        project.tasks.all().delete()
        project.links.all().delete()

        for node in nodes:
            Task.objects.create(
                project=project,
                task_id=str(node["id"]),
                name=node.get("name", "Untitled"),
                duration=int(node.get("duration", 10)),
                delay=int(node.get("delay", 0)),
                timestamp=node.get("timestamp", datetime.now().strftime("%I:%M %p")),
            )

        for link in links:
            source_id = link["source"] if isinstance(link["source"], str) else link["source"].get("id", "")
            target_id = link["target"] if isinstance(link["target"], str) else link["target"].get("id", "")
            Link.objects.create(
                project=project,
                source_task_id=str(source_id),
                target_task_id=str(target_id),
            )

        return JsonResponse({"status": "saved", **_serialize_project(project)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ──────────────────────────────────────────────
# API: AUTH
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def login_view(request):
    try:
        data = json.loads(request.body)
        username = data.get("username", "")
        password = data.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({
                "status": "authenticated",
                "username": user.username,
                "is_admin": user.is_staff or user.is_superuser,
            })
        else:
            return JsonResponse({"error": "Invalid credentials"}, status=401)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    return JsonResponse({"status": "logged_out"})

@csrf_exempt
@require_http_methods(["GET"])
def status_view(request):
    """Check current authentication status."""
    if request.user.is_authenticated:
        return JsonResponse({
            "status": "authenticated",
            "username": request.user.username,
            "is_admin": request.user.is_staff or request.user.is_superuser,
        })
    return JsonResponse({"status": "unauthenticated"}, status=401)

@csrf_exempt
@require_http_methods(["POST"])
def register_api_view(request):
    """Handle user registration."""
    try:
        data = json.loads(request.body)
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return JsonResponse({"error": "Username and password are required."}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username is already taken."}, status=400)

        user = User.objects.create_user(username=username, email=email, password=password)
        
        # Log them in automatically
        user = authenticate(request, username=username, password=password)
        login(request, user)
        
        return JsonResponse({
            "status": "registered_and_authenticated",
            "username": user.username,
            "is_admin": user.is_staff or user.is_superuser,
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ──────────────────────────────────────────────
# API: ADMIN USER ANALYTICS
# ──────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET"])
def admin_analytics(request):
    """Return system-wide analytics. Admin-only."""
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"error": "Admin access required"}, status=403)

    from django.db.models import Sum, Count, Avg

    users = User.objects.all()
    projects = Project.objects.all()
    tasks = Task.objects.all()
    links = Link.objects.all()

    total_delay = tasks.aggregate(total=Sum('delay'))['total'] or 0
    avg_duration = tasks.aggregate(avg=Avg('duration'))['avg'] or 0
    delayed_tasks = tasks.filter(delay__gt=0).count()
    on_track_tasks = tasks.filter(delay=0).count()

    # Per-user breakdown
    user_stats = []
    for u in users:
        user_projects = Project.objects.filter(owner=u)
        user_task_count = 0
        user_delay_total = 0
        user_project_names = []

        for p in user_projects:
            ptasks = p.tasks.all()
            user_task_count += ptasks.count()
            user_delay_total += sum(t.delay for t in ptasks)
            user_project_names.append(p.name)

        # Also count unowned projects for the first user or admin
        if not user_projects.exists():
            unowned = Project.objects.filter(owner__isnull=True)
            for p in unowned:
                ptasks = p.tasks.all()
                user_task_count += ptasks.count()
                user_delay_total += sum(t.delay for t in ptasks)
                user_project_names.append(p.name)

        user_stats.append({
            "username": u.username,
            "email": u.email or "—",
            "is_admin": u.is_staff or u.is_superuser,
            "is_active": u.is_active,
            "date_joined": u.date_joined.strftime("%Y-%m-%d %H:%M"),
            "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never",
            "projects": user_project_names,
            "total_tasks": user_task_count,
            "total_delay_days": user_delay_total,
        })

    return JsonResponse({
        "system": {
            "total_users": users.count(),
            "admin_users": users.filter(is_staff=True).count(),
            "total_projects": projects.count(),
            "total_tasks": tasks.count(),
            "total_links": links.count(),
            "total_delay_days": total_delay,
            "avg_task_duration": round(avg_duration, 1),
            "delayed_tasks": delayed_tasks,
            "on_track_tasks": on_track_tasks,
        },
        "users": user_stats,
    })
