all: delete-compiled-shit pip git
	echo "Done."

delete-compiled-shit:
	rm -R build/ dist/ ; rm -R luckydonald_utils.egg-info/ ; find . -name '*.pyc'
	find . -name '*.pyc' -delete ; True

upload: pip git

pip-build:
	uv run python scripts/build_modules.py --out build/modules --build

dev-dependencies:
	uv sync --group dev

test-pip: dev-dependencies
	uv run python scripts/build_modules.py --out build/modules --publish --repository-url https://test.pypi.org/legacy/

pip: dev-dependencies
	uv run python scripts/build_modules.py --out build/modules --publish

git:
	git push

bump: dev-dependencies
	uv run bump-my-version show-bump
	uv run bump-my-version bump patch
