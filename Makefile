VENV = source myvenv/bin/activate

.PHONY: server call

server:
	$(VENV) && cd django-backend && daphne backend.asgi:application

call:
	$(VENV) && python mock_twilio_client/mock_twilio_client.py

makemigrations:
	$(VENV) && cd django-backend && python manage.py makemigrations

migrate:
	$(VENV) && cd django-backend && python manage.py migrate	