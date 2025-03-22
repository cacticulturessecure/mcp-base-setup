from setuptools import setup, find_packages

setup(
    name="simple-anthropic-cli",
    version="4.0.0",
    description="CLI for Anthropic Claude with Gmail, Drive and tool use",
    author="SimpleAnthropicCLI Team",
    packages=find_packages(),
    install_requires=[
        "google-api-python-client>=2.100.0",
        "google-auth-httplib2>=0.1.0",
        "google-auth-oauthlib>=1.0.0",
        "requests>=2.28.0",
        "anthropic>=0.5.0",
        "python-dotenv>=1.0.0"
    ],
    entry_points={
        "console_scripts": [
            "simple-anthropic=simple_anthropic_cli:main",
        ],
    },
)