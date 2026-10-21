import os
from glob import glob

from setuptools import setup

package_name = 'tank_il'


def data_files_under(src_dir):
    """src_dir 以下のファイルを share/<pkg>/ 以下に同じ構造でインストールする"""
    result = []
    for root, _, files in os.walk(src_dir):
        if files:
            result.append((os.path.join('share', package_name, root),
                           [os.path.join(root, f) for f in files]))
    return result


setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml') + glob('config/*.config')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
    ] + data_files_under('models'),
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='anonymous',
    maintainer_email='noreply@example.com',
    description='Tracked vehicle imitation learning (ACT) on Ignition Gazebo',
    license='MIT',
    entry_points={
        'console_scripts': [
            'tank_driver = tank_il.tank_driver:main',
            'state_publisher = tank_il.state_publisher:main',
            'teleop_tank = tank_il.teleop_tank:main',
            'evaluate_berm = tank_il.evaluate_berm:main',
            'evaluate_ditch = tank_il.evaluate_ditch:main',
        ],
    },
)
