# Makefile for Smart Recipe & Inventory Manager
.PHONY: build up down restart app postgres ollama logs clean test dev

IMAGE_NAME="smart-recipe-inventory-manager"
TAG="latest"

build:
	./build.sh

up:
	docker-compose up --build -d
	down:
	docker-compose down

restart: down up

app:
	docker-compose exec app sh

postgres:
	docker-compose exec postgres psql -U app_user -d app_db

ollama:
	docker-compose exec ollama curl -s http://localhost:11434/api/version

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f

test:
	cd /c/Users/DELL/Desktop/IUT-BUT_info/BUT3/s5/sae/sae_smart/SAe_Smart_Finder && coverage run -m pytest

coverage:
	cd /c/Users/DELL/Desktop/IUT-BUT_info/BUT3/s5/sae/sae_smart/SAe_Smart_Finder && coverage report

dev:
	docker-compose up --build -d
	timer 5 sleep "Waiting for services..."
	echo "Application ready! Open http://localhost:7860"