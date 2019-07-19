# AlpacaTag
An Active Learning-based Crowd Annotation Framework for Sequence Tagging 
in Proc. of ACL 2019 (Demo Track) 

MIT License

<https://github.com/chakki-works/doccano>
## Features

* Collaborative annotation
* Language independent
* Active Learning & Online learning

## Requirements

* Python 3.6.5+
* django 2.0.5+
* Google Chrome(highly recommended)
* Pytorch

## Installation

**Setup Python environment**

First we need to install the dependencies. Run the following commands:

```bash
conda create -n alpaca python==3.6.5
conda activate alpaca
pip install -r requirements.txt
cd AlpacaTag
```

Install the server and client.

```bash
cd alpaca_client
python setup.py install
cd ..

# server packaging is not implemented yet.
cd alpaca_server
python setup.py install
cd ..
```

## Frontend (Django, Vue.js)

We need to compile the frontend. Run the following commands:

```bash
cd annotation/AlpacaTag/server
npm install
npm run build
cd ..
```

Next we need to make migration. Run the following command:

```bash
python manage.py migrate
```

Next we need to create a user who can login to the admin site. Run the following command:


```bash
python manage.py createsuperuser
```

Enter your desired username and press enter.

```bash
Username: admin
```

You will then be prompted for your desired email address:

```bash
Email address: admin@example.com
```

The final step is to enter your password. You will be asked to enter your password twice, the second time as a confirmation of the first.

```bash
Password: **********
Password (again): *********
Superuser created successfully.
```

**Running Django development server**

```bash
python manage.py runserver
```
Now, open a Web browser and go to <http://127.0.0.1:8000>.
If you run on your own server, use this command.

```bash
python manage.py runserver 0.0.0.0:8000
```

## Backend (Pytorch, ZeroMQ)

**Server-side**

```bash
cd alpaca_server/alpaca_serving/server
python main.py
```

**Client-side**

```bash
# get data for example
from alpaca_server.alpaca_model.pytorchAPI import *
x_train, y_train = utils.load_data_and_labels('train.bio')
sent = x_train[0:10]
label = y_train[0:10]


from alpaca_serving.client import *
ac = AlpacaClient()
ac.initiate(1)
ac.online_initiate(sent,[['B-PER', 'I-PER', 'B-LOC', 'I-LOC', 'B-ORG', 'I-ORG', 'B-MISC', 'I-MISC', 'O']])
active_indices = ac.active_learning(sent, acquire=5)
active_sent = [sent[a_i] for a_i in active_indices]
active_label = [label[a_i] for a_i in active_indices]
ac.online_learning(active_sent,active_label, epoch=5, batch=5)
ac.predict(‘New York and Paris’)
```


