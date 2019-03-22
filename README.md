# webpage-qa

This is a project to apply BloomburyAI's "Cape" (https://github.com/bloomsburyai/cape-webservices) model to web pages. Cape is a question-answer model that allows users to upload documents and ask natural language questions of those documents. This project describes a webapp which allows users to provide web page urls and ask questions of the web page's content.

## Overview

The main webapp is defined in App/questionAPI.py. It is designed to be accessed through a browser. The app also exposes an API with the following methods:

Route | Type | Description
---|---|---
/questionsAPI | POST | The main entry point. It accepts POST requests containing a url and question, returns the answer and the answer "context" (the extracted text from the web page which the model has determined contains the answer).
/questionsAPI/documentsAPI | GET | Returns the IDs, titles and contents of the web pages that have been submitted.
/questionsAPI/documentsAPI/{ID} | GET | Returns the title and contents of the web pages with the given ID.
/questionsAPI/answersAPI" | GET | Returns the questions that have been submitted, together with their IDs, associated answers and answer contexts.
/questionsAPI/answersAPI/{ID}" | GET | Returns the question with the given ID, together with its associated answer and answer context.
 
## Deployment

The webapp is designed for cloud deployment using Kubernetes. The app's structure is outlined and discussed below.

![alt text](https://github.com/richardbatstone/webpage-qa/blob/master/deployment_graphic.png "Deployment structure")

#### questionAPI

questionAPI is a Python Flask webapp and the project's entry point. It is designed to be accessed through a brower and populates the small number of templates in App/templates/. The app is served with Flask's built-in server (rather than a production server, see further work below). For deployment, the app is containerised and exposed on a public IP address at port 80 with a "LoadBalancer" service. By default, 1 replica set is created.

#### mercury-parser

Mercury-parser is a micro-service which parses web pages and extracts their content. It is based on Postlight's Mercury-parser (https://github.com/postlight/mercury-parser), which is a node package, and exposed in a simple node express server. It was developed for this project and separately described here: https://github.com/richardbatstone/mercury_server. For deployment, the server is containerised and accessed with a "selector" service (Kubernetes_deployment/mercury-parser-service.yaml). The host and port clusterIP of the service are accessible in the other pods in the cluster as environment variables. By default, 1 replica set is created.

#### database

The project includes a Cassandra database which stores: (i) documents (i.e. web pages) which are queried; and (ii) questions which are submitted and their associated answers. The database is deployed (as a replication controller) using a public Cassandra image. Like the mercury-parser, the deployment is accessed with a "selector" service. The webapp reads and writes to the database using Cassandra Driver (https://datastax.github.io/python-driver/index.html), a Python client driver for Cassandra. By default, 1 replica set is created.

#### CapeAPI

The CapeAPI does not currently form part of the Kubernetes deployment (see further work below). Instead, Cape must be launched separately and accessed as an external resource. The steps to deploy Cape and access it from the project are:

 - deploy the Cape docker image to a virtual machine (docker.io/bloomsburyai/cape:latest);
 - run the setup code below; and
 - add the CapiAPI base and admin token to the app's frontend deployment (Kubernetes_deployment/frontend-deployment.yaml) so they can be accessed as environment variables within the cluster.
 
 ```bash
 
 # Pass a test question
 
 curl 'http://localhost:5050/api/0.1/answer?token=demo&question=Who+heads+the+board?&text=The+board+is+represented+by+the+chairman'
 
 # Set up a user (replace password and token with a user password and token)
 
 curl -v "http://localhost:5050/api/0.1/user/create-user?userId=user_1&password=password&token=token&superAdminToken=REPLACEME"
 
 # Log the user in and return the admin token
 
 curl -v "http://localhost:5050/api/0.1/user/login?login=user_1&password=password"
 
 ```
 #### Setup
 
 The Kubernetes configuration files are included in Kubernetes_deployment/. The webapp can be deployed on Google Cloud Platform, for example, by:
 
 ```bash
 # Set up a cluster
 
 gcloud config set compute/zone europe-west1-b
 gcloud container clusters create webpage-qa --num-nodes=3 --machine-type "n1-standard-2"
 
 # Kubernetes deployment
 
 kubectl create -f cassandra-peer-service.yaml
 kubectl create -f cassandra-service.yaml
 kubectl create -f cassandra-replication-controller.yaml
 kubectl create -f mercury-parser-deployment.yaml
 kubectl create -f mercury-parser-service.yaml
 kubectl create -f frontend-deployment.yaml
 kubectl create -f frontend-service.yaml
 
 # Wait for public IP address
 
 kubectl get service webpage-qa --watch
 
 # The deployments can then be scaled in the usual way
 
 kubectl scale deployment webpage-qa --replicas=3
 kubectl scale deployment mercury-parser --replicas=3
 kubectl scale rc cassandra --replicas=3
 
 # Check the Cassandra ring has been formed
 
 kubectl exec -it cassandra-lwfvw -- nodetool status
 ```
 
 ## Further work

The project is in development and there is clearly scope for further work / additional functionality. For example:

 - bring Cape within the Kubernetes deployment (which would allow scaling of the service, which is the key bottleneck in the app's responsiveness);
 - add user profiles and other security features;
 - deploy the flask app to a WSGI server; and
 - add smarter load balancing access.
