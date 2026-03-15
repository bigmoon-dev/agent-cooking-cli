from setuptools import find_packages, setup


setup(
    name="agent-cooking-cli",
    version="0.1.0",
    description="Evidence-first, artifact-driven bug triage workflow for CLI agents",
    package_dir={"": "src"},
    packages=find_packages("src"),
    install_requires=[
        "typer>=0.9.0",
        "PyYAML>=6.0.1",
    ],
    entry_points={
        "console_scripts": [
            "kitchen=triageflow.cli:app",
        ]
    },
    include_package_data=True,
)
