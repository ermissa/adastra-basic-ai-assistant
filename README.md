#  Speech Assistant with Twilio Voice and the OpenAI Realtime API (Python)
### install python dependencies
```
pip install -r requirements.txt
python -m pip install daphne
```

### Run the Database and Apply Migrations

1. Make sure Docker and Docker Compose are installed on your system.
2. Navigate to the `docker-compose` directory containing the `docker-compose.postgresql.yml` file and start the PostgreSQL container using the following command:

```bash
docker-compose -f docker-compose.postgresql.yml up
```

3. Once the PostgreSQL container is running, go to the django-backend directory and apply the migrations with:

```bash
python3 manage.py makemigrations
python3 manage.py migrate
```

or you can use Makefile commands in root directory:

```bash
make makemigrations
make migrate
```

### start server
```
cd django-backend
daphne backend.asgi:application
```

### start a test call
```
python mock_twilio_client/mock_twilio_client.py
```