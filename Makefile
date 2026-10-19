all: delete-compiled-shit pip git
	echo "Done."

delete-compiled-shit:
	rm -R build/ dist/ ; rm -R luckydonald_utils.egg-info/ ; find . -name '*.pyc'
	find . -name '*.pyc' -delete ; True

upload: pip git

pip-build:
	uv build

dev-dependencies:
	uv sync --group dev

test-pip: pip-build dev-dependencies
	uv run twine upload --username luckydonald --skip-existing --repository-url https://test.pypi.org/legacy/ dist/*

pip: pip-build
	uv run twine upload --username luckydonald --skip-existing dist/*

git:
	git push

bump: dev-dependencies
	uv run bump-my-version show-bump
	uv run bump-my-version bump patch
