#!/usr/bin/env python3
"""Login único no Garmin Connect para gerar o token usado pela automação.

Rode no SEU computador (não no GitHub):
  pip install -r requirements.txt
  python tools/garmin_login.py

Ele pede e-mail, senha e, se houver, o código de verificação (MFA).
No fim imprime um JSON: copie e salve como secret GARMIN_TOKENS no repositório
(Settings > Secrets and variables > Actions > New repository secret).
A senha não é salva em lugar nenhum.
"""
import getpass

from garminconnect import Garmin


def main() -> None:
    email = input("E-mail do Garmin Connect: ").strip()
    pwd = getpass.getpass("Senha: ")
    api = Garmin(email, pwd, prompt_mfa=lambda: input("Código de verificação (MFA): ").strip())
    api.login()
    print("\nLogin OK. Copie a linha abaixo inteira para o secret GARMIN_TOKENS:\n")
    print(api.client.dumps())
    print("\nTrate esse texto como senha: ele dá acesso à sua conta Garmin.")


if __name__ == "__main__":
    main()
