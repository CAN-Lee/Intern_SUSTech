FROM python:3.11-slim
RUN pip install --no-cache-dir numpy==2.2.6 scipy==1.15.3 trimesh==4.7.4 rtree==1.4.1 scikit-image==0.25.2 matplotlib==3.10.3 Pillow==11.2.1
RUN pip install --no-cache-dir numpy==1.26.4 trimesh==5.1.0 embreex==2.17.7
ENV PYTHONPATH=/opt/rsi OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/mpl PYTHONDONTWRITEBYTECODE=1 HOME=/home/user
WORKDIR /home/user/evolution_project
CMD ["sleep", "infinity"]
