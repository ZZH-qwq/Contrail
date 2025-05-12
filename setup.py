from setuptools import setup, find_packages

setup(
    name="contrail",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": ["contrail = contrail.cli:main"],
    },
    install_requires=[
        "altair",
        "loguru",
        "numpy",
        "nvidia-ml-py",
        "openpyxl",
        "pandas",
        "pillow",
        "plotly",
        "psutil",
        "schedule",
        "selenium",
        "streamlit",
        "streamlit-autorefresh",
        "streamlit-javascript",
        "user-agents",
    ],
)
