=============================================
How to control this glue service with systemd
=============================================

1. Check that you have the correct host url and token by testing from the command line::

        cd ../src/
        python3 argus_pomodoro.py HOST TOKEN --check --debug

2. Copy the .service file that is in this directory to the systemd directory::

        sudo mv ./argus_pomodoro.service /etc/systemd/system/
        sudo chown root:root /etc/systemd/system/argus_pomodoro.service
        sudo chmod 644 /etc/systemd/system/argus_pomodoro.service

3. Create a user to run the service as::

        sudo useradd -r -s /bin/false argus_pomodoro

4. Either copy the python-script to a suitable directory for binaries or install it with pip.

   a. Copying the python-script::

        sudo cp ../src/argus_pomodoro.py /usr/local/bin/

   b. Pip install the python-script::

        cd ../
        sudo pip install .

5. Update the .service file:

   * Replace USERNAME with argus_pomodoro
   * Replace PATH:

        * If you copied the file: ``/usr/local/bin/argus_pomodoro.py``
        * If you pip installed: ``${which argus_pomodoro}/argus_pomodoro``

6. Tell systemctl about the service::

        sudo systemctl daemon-reload
        sudo systemctl enable argus_pomodoro.service
        sudo systemctl restart argus_pomodoro.service

7. Check that it is up and running::

        systemctl status argus_pomodoro.service
