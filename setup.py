from setuptools import setup, find_packages

base_requires = [
    "loguru",
    "numpy",
    "nvidia-ml-py",
    "pandas",
    "psutil",
    "schedule",
]

ai4s_requires = ["selenium", "openpyxl"]

web_requires = [
    "altair",
    "pillow",
    "plotly",
    "streamlit",
    "streamlit-autorefresh",
    "streamlit-javascript",
    "user-agents",
]

setup(
    name="contrail",
    version="0.1",
    packages=find_packages(),
    entry_points={
        "console_scripts": ["contrail = contrail.cli:main"],
    },
    install_requires=base_requires,
    extras_require={
        "ai4s": ai4s_requires,
        "web": web_requires,
    },
)
