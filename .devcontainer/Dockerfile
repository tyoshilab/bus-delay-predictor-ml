FROM python:3.11-slim
WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y python3-tk libpq-dev
RUN pip install numpy
RUN pip install pandas
RUN pip install matplotlib
RUN pip install seaborn
RUN pip install openpyxl
RUN pip install scikit-learn
RUN pip install psycopg2-binary
RUN pip install tensorflow
RUN pip install ipykernel