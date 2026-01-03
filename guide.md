# Guide for using the system

```bash
python -m venv venv
```

```bash
source venv/Scripts/activate
```

```bash
pip install flask requests matplotlib gevent tinyrpc protobuf pyzmq boto3 apschedul
```

```bash
python3 -m pip install git+http://git@github.com/steinwurf/pyerasure
```

```bash
deactivate
```

Change the config file found in dsm/config.py to set buddy size for grps, the number of fragments a file should be split into etc.

Run the script with an argument for how many nodes need to be started e.g. ```./script.sh 6```

Run a measurements file found in analysis/measurements.py or analysis/measurements2.py to start collecting data.
