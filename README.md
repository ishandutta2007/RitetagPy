# RitetagPy
Automated Instgram scheduler via Ritetag

## Installation:

```
pip install --upgrade pip
curl https://pyenv.run | bash
pyenv install 3.6.0
pyenv local 3.6.0
pip install -r requirements.txt
```
 
## How to run:

- Modify multiuser_quickstart.py accoding to your accounts.
- `python quickstart.py -u <fb_userid> -p <fb_password>`

## Cron:

Schedule cron job like this(daily at 3am):

- `0 3 * * * bash /path/to/RitetagPy/run_allinone_ritetagpy_only_once_for_mac.sh /path/to/RitetagPy/quickstart.py`
