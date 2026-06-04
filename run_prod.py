from werkzeug.middleware.dispatcher import DispatcherMiddleware
from app import app as guest_app, init_db
from admin_app import app as admin_app, run_migrations_and_seed

# Initialize base database tables if they don't exist
init_db()

# Run database migrations and seed default admin credentials on startup
run_migrations_and_seed()

# Merge both apps: serving guest site on '/' and admin panel on '/admin'
application = DispatcherMiddleware(guest_app, {
    '/admin': admin_app
})

if __name__ == "__main__":
    from werkzeug.serving import run_simple
    print("Starting Clutch Hotel Portal on http://localhost:5000")
    print("Front Desk Desk operations at: http://localhost:5000/")
    print("Administrative dashboard at: http://localhost:5000/admin")
    run_simple('localhost', 5000, application, use_reloader=True, use_debugger=True)

