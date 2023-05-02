import sys
import pynautobot

# import os
from jinja2 import Environment, FileSystemLoader
import datetime

date = datetime.date.today()
Nautobot_URL = sys.argv[1]
Nautobot_Token = sys.argv[2]


nautobot = pynautobot.api(
    url=Nautobot_URL, token=Nautobot_Token, threading=True
)

ENV = Environment(loader=FileSystemLoader("/runner/project/playbooks/files/"))
template = ENV.get_template("nautobot_connected_devices.j2")

connected_devices = []

output_list = []

leaf_switches = nautobot.dcim.devices.filter(role="leaf")
spine_switches = nautobot.dcim.devices.filter(role="spine")
all_devices = nautobot.dcim.devices.all()
all_interfaces = nautobot.dcim.interfaces.filter(
    name__nisw="Vlan", connected=True
)
lag_interfaces = nautobot.dcim.interfaces.filter(type="lag")

# ignored_roles = ['spine', 'leaf', 'border-services-leaf']

for i in all_interfaces:
    if all(
        [
            i.device in leaf_switches,
            i.connected_endpoint.device.name not in connected_devices,
            i.connected_endpoint.device not in leaf_switches,
            i.connected_endpoint.device not in spine_switches,
        ]
    ):
        connected_devices.append(i.connected_endpoint.device.name)

# At this point I have a list of devices connected to my switches.
connected_devices.sort()

# Check each connected device,
# find its switchport and document settings into dictionary
for cd in connected_devices:
    for i in all_devices:
        if i.name == cd:
            device_rack = i.rack
            device_url = i.url.replace("/api", "")

    # lists to collect adapter info
    endpoint_list = []
    switchport_list = []
    switch_list = []
    adapter_list = []
    lag_endpoint_list = []
    lag_switchport_list = []
    lag_switch_list = []
    lag_int_mode = ""
    lag_int_vlans = ""
    int_mode = ""
    switch_mlag_tag = ""
    lag_interface = False

    for interface in all_interfaces:
        if interface.connected_endpoint.device.name == cd:
            port_enabled = interface.enabled
            switch_int_tag = ""

            # If Port is part of a LAG
            if interface.lag:
                lag_endpoint_list.append(interface.connected_endpoint.name)
                lag_switchport_list.append(interface.name)
                lag_switch_list.append(interface.device.name)
                lag_interface = True
                if interface.tags:
                    switch_mlag_tag = interface.tags[0].name.strip(
                        "port-profile_"
                    )

                for lag in lag_interfaces:
                    if lag.id == interface.lag.id:
                        if lag.mode:
                            if (lag.mode.value == "access") and (
                                lag.untagged_vlan
                            ):
                                lag_int_vlans = lag.untagged_vlan.vid
                                lag_int_mode = "access"
                            elif lag.mode.value == "tagged-all":
                                lag_int_mode = "trunk"
                        if lag.tags:
                            switch_mlag_tag = lag.tags[0].name.strip(
                                "port-profile_"
                            )
                        else:
                            continue

            # if Port is not part of a LAG
            else:
                endpoint_list = []
                switchport_list = []
                switch_list = []
                int_vlans = ""
                endpoint_list.append(interface.connected_endpoint.name)
                switchport_list.append(interface.name)
                switch_list.append(interface.device.name)

                if (interface.mode.value == "access") and (
                    interface.untagged_vlan
                ):
                    int_vlans = interface.untagged_vlan.vid
                    int_mode = "access"
                elif interface.mode.value == "tagged-all":
                    int_mode = "trunk"
                # else:
                #     continue

                if interface.tags:
                    switch_int_tag = interface.tags[0].name.strip(
                        "port-profile_"
                    )

                # Add all the info to adapter dict
                # and append to list of adapters
                adapters = {
                    "endpoint_ports": endpoint_list,
                    "switch_ports": switchport_list,
                    "switches": switch_list,
                    "mode": int_mode,
                    "vlans": int_vlans,
                    "enabled": port_enabled,
                    "profile": switch_int_tag,
                }
                adapter_list.append(adapters)

    # if port was part of mlag, add it to list
    if lag_interface:
        adapters = {
            "endpoint_ports": lag_endpoint_list,
            "switch_ports": lag_switchport_list,
            "switches": lag_switch_list,
            "mode": lag_int_mode,
            "vlans": lag_int_vlans,
            "lag": True,
            "enabled": port_enabled,
            "profile": switch_mlag_tag,
        }
        adapter_list.append(adapters)

    # add all info to my dict
    connected_device_dict = {
        "connected_device": cd,
        "device_url": device_url,
        "rack": device_rack,
        "adapters": adapter_list,
    }

    output_list.append(connected_device_dict)

# Parse the info via Jinja
yml_output = template.render(
    connected_device=output_list, trim_blocks=True, lstrip_blocks=True
)

# Over write the existing yml
file = open(
    "/tmp/awx-repo/inventory/group_vars/CONNECTED_ENDPOINTS/nautobot_connected_devices.yml",
    "w",
)
file.write(yml_output)
file.close

print(yml_output)
