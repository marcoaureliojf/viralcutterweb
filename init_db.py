"""
Script to initialize the database and create a default project for migration.
Run this once to set up the database.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, SessionLocal
from database import crud

def main():
    print("🔧 Inicializando banco de dados...")
    
    # Initialize database tables
    init_db()
    
    # Create a database session
    db = SessionLocal()
    
    try:
        # Check if there are any projects
        projects = crud.get_all_projects(db)
        
        if not projects:
            print("\n📁 Criando projeto padrão...")
            default_project = crud.create_project(
                db=db,
                name="Projeto Padrão",
                description="Projeto criado automaticamente para vídeos existentes"
            )
            
            # Create project directories
            project_dir = f"projects/{default_project.id}"
            for subdir in ["uploads", "outputs", "tmp", "burned_sub", "subs_ass"]:
                os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)
            
            print(f"✅ Projeto padrão criado: {default_project.name} (ID: {default_project.id})")
            print(f"   Use este ID para fazer upload de vídeos: {default_project.id}")
        else:
            print(f"\n✅ Banco de dados já possui {len(projects)} projeto(s)")
            for project in projects:
                print(f"   - {project.name} (ID: {project.id})")
    
    finally:
        db.close()
    
    print("\n🎉 Inicialização concluída!")

if __name__ == "__main__":
    main()
