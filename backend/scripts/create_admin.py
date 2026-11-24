"""Cria ou eleva uma conta administrativa por comando explícito local."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db.session import SessionLocal  # noqa: E402
from app.main import _cpf_fingerprint, _fernet, password_hash  # noqa: E402
from app.models import User  # noqa: E402
from app.schemas import valid_cpf  # noqa: E402


def main():
    email = input("E-mail do administrador: ").strip().lower()
    name = input("Nome: ").strip()
    cpf = valid_cpf(input("CPF (será cifrado): "))
    address = input("Endereço comercial: ").strip()
    password = getpass.getpass("Senha (mínimo 12 caracteres): ")
    if len(password) < 12:
        raise SystemExit("A senha precisa ter pelo menos 12 caracteres.")
    if password != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem.")
    db = SessionLocal()
    try:
        existing_email = db.query(User).filter_by(email=email).first()
        if existing_email:
            existing_email.role = "admin"
            existing_email.is_active = True
            db.commit()
            print("Conta existente promovida a administradora; senha e CPF não foram alterados.")
            return
        user = User(name=name, email=email, password_hash=password_hash.hash(password),
                    cpf_encrypted=_fernet().encrypt(cpf.encode()).decode(), cpf_fingerprint=_cpf_fingerprint(cpf),
                    business_address=address, role="admin", is_active=True)
        db.add(user); db.commit()
        print("Conta administradora criada.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
