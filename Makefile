all: vk.py libvulkan.json
	python example.py

vk.py: vkstruct.py spec/vk.xml
	python vkstruct.py > vk.py

libvulkan.json: vkstruct_json.py spec/vk.xml
	python vkstruct_json.py
