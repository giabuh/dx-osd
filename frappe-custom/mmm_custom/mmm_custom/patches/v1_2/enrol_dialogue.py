# Copyright (c) 2026 DX-OSD contributors
# SPDX-License-Identifier: MIT

from mmm_custom.demo.loader import load_register_skill


def execute():
	# D-121: the bot leads a registration through the class and the phone before handing off.
	load_register_skill()
