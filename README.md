# Nautobot-to-AVD
The goal of this repo is to show how you may use Nautobot as a SoT for devices connecting to leafs in an Arista AVD generated S/L configuration.

[Arista AVD](https://avd.sh) does a great job of building out the Spine/Leaf network from your YML files defining how the network should operate.  My team has deployed this successfully and one caveat is managing connected devices to the leafs.  Manually adding devices to the YML files is tedious if you're dealing with a large number of devices.  This repo was a Proof of Concept on how to get the meaningful data out of Nautobot and convert it to an AVD friendly format.  It forces documentation to always be up to date because if a device isn't connected within Nautobot, the configuration will never be added to the switch.  If you decommission a device from Nautobot the corresponding configuration is then removed from the switches.

**Please note that I am not a real dev, use this at your own risk**

If you do have suggestions on improving it I'm welcome to feedback

## Repo Structure
For this repo we are using the following directory structure for Arista AVD
```
inventory/
├─ group_vars/
│  ├─ CONNECTED_DEVICES/
│  │  ├─ nautobot_connected_devices.yml
playbooks/
├─ files/
│  ├─ nautobot_connected_devices.j2
│  ├─ nautobot_connected_devices.py
├─ pb_Update_Connected_Devices.yml
```

## Job Workflow
To give an idea of how this works with Nautobot here is an example workflow.

1. Update Nautobot with the connected device.
    - Option 1 - This may be done manually through Nautobot GUI
    - Option 2 - Add connections via API
    - Option 3 - Run custom Nautobot Job to prompt for connections
2. Once Nautobot is up to date with connections, launch the Ansible playbook `pb_Update_Connected_Devices.yml` to update the relevant YML file.
    - We execute the job via Ansible AWX
    - Nautobot URL and Token are passes as sysargs from the AWX vault
    - Ansible job isn't required, you could run the python file manually
    1. The job clones the repo to a local /tmp location
    2. The second task runs the Python script `nautobot_connected_devices.py` to update the YML file via Nautobot information.  More info below..
    3. The last task pushes changes back to the repo
3. We have a webhook on our repo, so once a push occurs the webhook will trigger the normal AVD deployment job.
    - This is what makes changes to the file active in our S/L environment

## naubot_connected_devices.py information and flow
To help explain how the job works here is the flow.  Remember, I'm not a real dev so there are probably 1000 ways this could be improved.
- Pynautobot is used for interaction with Nautobot

1. The Nautobot URL and Token are passed in as `sys.argv`
2. `ENV` sets the path relevant to our AWX environment.  Adjust this as you need `/runner/project/playbooks/files/`
3. `Template` is referring to the Jinja template used to turn output into AVD friendly YML.
4. We query Nautobot for devices and interfaces, we gather;
    - Leafs
    - Spines
    - All devices
    - All interfaces (Excluding VLAN SVI's, and only includes connected)
    - LAG interfaces
5. We now loop over all the interfaces that were returned to make a list of all things connected to leafs.
    - Only devices connected to leafs
    - Not already in the list
    - Not leaf switches, ignore MLAG links for example
    - Not spine switches, ignore S-L connections
6. We now have a sorted list of everything connected to the leafs.  Loop over the list to gather relevant data
    - Rack
    - URL for documentation
    - Adapter list
    - LAG info
    - VLAN / Port information
7. For each device now loop over the interfaces to gather the ones connected to our S/L switches. Same with LAG interfaces, gather all needed info
8. Once all interface information has been gathered for the device, add to the output_list for processing by Jinja
9. At this point, all devices have been reviewed, pass the output_list over the Jinja template to convert to AVD friendly YML.
    - File is `/tmp/awx-repo/inventory/group_vars/CONNECTED_ENDPOINTS/nautobot_connected_devices.yml` per our AWX environment, adjust for your path.

## Ansible Playbook info
Notes about the playbook are here, to help explain the intent.
- The first play uses the collection [lvrfrc87.git_acp](https://github.com/lvrfrc87/git-acp-ansible) to clone the Repo to a local temp folder.
- AWX passes in the SSH keys needed for repo management via the key file.
- Pushing to the repo is via the `git_acp` module