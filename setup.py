from setuptools import setup, find_packages

setup(
        name="aioreq",
        version='0.0.1',
        description="Async requests lib",
        install_requires = [
            'dnspython',
            'certifi'
            ],
        packages = find_packages(),
        include_package_data=True,
        package_data={'aioreq':['*.ini']}
        )
