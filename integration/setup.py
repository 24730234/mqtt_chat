"""Generate local-only database credentials once; never overwrite existing values."""
from pathlib import Path
import secrets

path = Path(__file__).with_name('.env')
try:
    with path.open('x') as file:
        file.write('MYSQL_PASSWORD=' + secrets.token_urlsafe(24) + '\n')
        file.write('MYSQL_ROOT_PASSWORD=' + secrets.token_urlsafe(24) + '\n')
    path.chmod(0o600)
    print('Created integration/.env (ignored by Git).')
except FileExistsError:
    print('Using existing integration/.env.')
