build-image:
	docker build --no-cache -t amiranda/meetup-scraper .

push-image:
	docker push amiranda/meetup-scraper

run-docker:
	docker run --rm amiranda/meetup-scraper $(ARGS)