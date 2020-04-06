from setuptools import find_packages, setup

setup(
    name="VMN webdemo",
    version="0.0.1",
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=["Flask", "Flask-WTF"],
)
