
service_name="wordle_alarm"
python_version="3.12"

set -e  # Exit immediately if a command exits with a non-zero status

echo "✅ Creating conda environment: $service_name with Python $python_version"
if ! conda env list | grep -q "^$service_name\s"; then
    conda create -n $service_name python=$python_version -y
else
    echo "✅ Conda environment '$service_name' already exists. Skipping creation."
fi

echo "✅ Activating conda environment: $service_name"
source /home/mnalavadi/miniconda3/etc/profile.d/conda.sh
conda activate $service_name

echo "✅ Installing required Python packages"
pip install -U poetry
poetry install --no-root

echo "✅ Installing playwright"
playwright install chromium
playwright install-deps

echo "✅ Copying service file to systemd directory"
sudo cp install/projects_${service_name}.service /lib/systemd/system/projects_${service_name}.service

echo "✅ Setting permissions for the service file"
sudo chmod 644 /lib/systemd/system/projects_${service_name}.service

echo "✅ Reloading systemd daemon"
sudo systemctl daemon-reload
sudo systemctl daemon-reexec

echo "✅ Enabling the service: projects_${service_name}.service"
sudo systemctl enable projects_${service_name}.service
sudo systemctl restart projects_${service_name}.service
sudo systemctl status projects_${service_name}.service --no-pager

echo "✅ Setup completed successfully! 🎉"
