# WebPage-qa

To do...

Got docker image of webpage QA. Can deploy externally (need to manually turn on firewall access to tcp:80)
Next, amend flask app so that can attach to backend service in kubernetes. See here: https://medium.com/@abhilashkjanardhanan/kubernetes-python-app-loadbalancer-connect-with-python-api-in-cluster-ip-service-75c7f433adc6

Kubernetes cluster:

# pull or clone this respoitory
git [clone][pull] https://github.com/richardbatstone/webpage-qa

# set compute zone
gcloud config set compute/zone europe-west1-b

# set up cluster
gcloud container clusters create webpage-qa --num-nodes=3 --machine-type "n1-standard-1"

# Deploy marcury parser "backend"
kubectl create -f mercury-parser-deployment.yaml

kubectl get deployment mercury-parser  see the deployment
kubectl get pods  see pods
kubectl get pods --all-namespaces  see all pods
gcloud compute instances list  see instances and ip addresses

can check things are working by:
kubectl exec -it [pod_name] bash
curl http://localhost:8080/ // should see some html.
exit // to exit

# Create backend service

kubectl create -f mercury-parser-service.yaml // create the service
kubectl describe svc mercury-parser // to get the service ip and port.
you can then exec -it backinto any node and curl the service ip and port.

Set webpage-qa parameters (cape api base, admin and mercury-server address) (find a way to automate this)

kubectl create -f frontend-deployment.yaml  (frontend deployemnt)
kubectl describe deployment webpage-qa (check its working)
kubectl create -f frontend-service.yaml  (frontend service)
kubectl describe svc webpage-qa (check its working)
kubectl get service webpage-qa --watch (untill you get an external IP)

Then use that IP






