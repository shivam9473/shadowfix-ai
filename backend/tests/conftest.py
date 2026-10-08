import os

os.environ["QDRANT_MODE"] = "memory"
os.environ["SHADOWFIX_ENV"] = "test"
os.environ["ADMIN_API_KEY"] = "test-admin"
os.environ.pop("GITHUB_TOKEN", None)
os.environ.pop("SHADOWFIX_OPEN_PR", None)
os.environ.pop("E2B_API_KEY", None)
os.environ.pop("SHADOWFIX_DEPLOY_ROLE_ARN", None)
