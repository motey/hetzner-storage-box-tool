from setuptools import setup
from pathlib import Path

readme_dir = Path(__file__).parent
readme_file = readme_dir / "README.md"
if readme_file.is_file():
    long_description = (readme_dir / "README.md").read_text()
else:
    long_description = ""

setup(
    name="hsbt",
    description="Collection of scripts wrapped into a python based CLI-bash-tool for common tasks with a hetzner storage box.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    author="Tim Bleimehl",
    license="MIT",
    packages=["hsbt"],
    install_requires=["pydantic", "click","pyaml"],
    extras_require={"test": []},
    python_requires=">=3.10",
    zip_safe=False,
    include_package_data=True,
    use_scm_version={
        "root": ".",
        "relative_to": __file__,
        # "local_scheme": "node-and-timestamp"
        "local_scheme": "no-local-version",
        "write_to": "version.py",
    },
    setup_requires=["setuptools_scm"],
    entry_points={"console_scripts": ["hsbt=hsbt.cli:cli"]},
)
