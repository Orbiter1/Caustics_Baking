import bpy
import json


# converts a blender Nodegroup to a json string
def export_node_group_to_json(name):
    if bpy.data.node_groups.find(name) == -1:
        return -1

    nodeTree = bpy.data.node_groups[name]
    nodeGroup = {
        'type': nodeTree.type,
        'interface': [],
        'nodes': [],
        'links': []
    }

    # storing the in and outputs of the Tree
    for i in nodeTree.interface.items_tree:
        if i.item_type == 'SOCKET':
            item = {
                'in_out': i.in_out,
                'name': i.name,
                'socket_type': i.socket_type,
                'default_attribute_name': i.default_attribute_name,
                'hide_value': i.hide_value
            }
            match i.socket_type:
                case 'NodeSocketFloat':
                    item['default_value'] = i.default_value
                    item['min_value'] = i.min_value
                    item['max_value'] = i.max_value
                    item['subtype'] = i.subtype
                case 'NodeSocketVector':
                    item['default_value'] = (i.default_value[0], i.default_value[1], i.default_value[2])
                    item['min_value'] = i.min_value
                    item['max_value'] = i.max_value
                    item['subtype'] = i.subtype
                case 'NodeSocketColor':
                    item['default_value'] = (i.default_value[0], i.default_value[1], i.default_value[2], i.default_value[3])
            nodeGroup['interface'].append(item)

    # storing all nodes of the Tree
    for n in nodeTree.nodes:
        inputs = {}
        for i in n.inputs:
            match i.type:
                case 'VALUE':
                    inputs[i.identifier] = i.default_value
                case 'RGBA':
                    inputs[i.identifier] = (
                        i.default_value[0], i.default_value[1], i.default_value[2], i.default_value[3])
                case 'VECTOR':
                    inputs[i.identifier] = (i.default_value[0], i.default_value[1], i.default_value[2])
                case 'STRING':
                    inputs[i.identifier] = i.default_value
                case 'INT':
                    inputs[i.identifier] = i.default_value
                case 'BOOLEAN':
                    inputs[i.identifier] = i.default_value

        attributes = {}
        for a in [attribute for attribute in n.bl_rna.properties.keys() if
                  attribute not in bpy.types.Node.bl_rna.properties.keys()]:
            if getattr(n, a) is not None:
                if a == 'node_tree':
                    attributes[a] = n.node_tree.name
                else:
                    attributes[a] = getattr(n, a)

        node = {
            'name': str(n.name),
            'type': str(n.__class__.__name__),
            'location': (n.location.x, n.location.y),
            'inputs': inputs,
            'attributes': attributes
        }

        nodeGroup['nodes'].append(node)

    # store all connections in Tree
    for l in nodeTree.links:
        link = {
            'from_node': str(l.from_node.name),
            'to_node': str(l.to_node.name),
        }
        for socket in l.from_node.outputs:
            if socket == l.from_socket:
                link['from_socket'] = socket.identifier
        for socket in l.to_node.inputs:
            if socket == l.to_socket:
                link['to_socket'] = socket.identifier
        nodeGroup['links'].append(link)

    return (json.dumps(nodeGroup))


# uses a json created with the export function to rebuild the blender nodegroup
def import_node_group_from_json(name, data):
    if data.replace(" ", "") != str(export_node_group_to_json(name)).replace(" ", ""):
        # Save all nodeGroups with this Nodetree for reassignment with the new tree
        node_groups = []
        for nodeGroup in bpy.data.node_groups:
            for node in nodeGroup.nodes:
                if str(node.__class__.__name__) == 'ShaderNodeGroup':
                    if node.node_tree is not None and node.node_tree.name == name:
                        node_groups.append(node)
        for material in bpy.data.materials:
            if material.node_tree is not None:
                for node in material.node_tree.nodes:
                    if str(node.__class__.__name__) == 'ShaderNodeGroup':
                        if node.node_tree is not None and node.node_tree.name == name:
                            node_groups.append(node)

        data = json.loads(data)
        # creating new node tree and deleting existing with same name
        if bpy.data.node_groups.__contains__(name):
            bpy.data.node_groups.remove(bpy.data.node_groups[name])
        match data['type']:
            case 'SHADER':
                node_tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
            case 'GEOMETRY':
                node_tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')

        # creating in and outputs of the tree
        for i in data['interface']:
            item = node_tree.interface.new_socket(i['name'], in_out=i['in_out'], socket_type=i['socket_type'])
            item.default_attribute_name = i['default_attribute_name']
            item.hide_value = i['hide_value']
            match i['socket_type']:
                case 'NodeSocketFloat':
                    item.default_value = i['default_value']
                    item.min_value = i['min_value']
                    item.max_value = i['max_value']
                    item.subtype = i['subtype']
                case 'NodeSocketVector':
                    item.default_value = i['default_value']
                    item.min_value = i['min_value']
                    item.max_value = i['max_value']
                    item.subtype = i['subtype']
                case 'NodeSocketColor':
                    item.default_value = i['default_value']

        # creating the nodes of the tree
        nodes = node_tree.nodes
        nodes.clear()
        for n in data['nodes']:
            node = nodes.new(n['type'])
            node.name = n['name']
            node.location = n['location']

            for atr, value in n['attributes'].items():
                if atr is not None:
                    if atr == 'node_tree':
                        node.node_tree = bpy.data.node_groups[value]
                    else:
                        setattr(node, atr, value)

            if not n['type'] == 'NodeReroute':
                for id, default in n['inputs'].items():
                    if default is not None:
                        for input in node.inputs:
                            if input.identifier == id:
                                input.default_value = default

        # connecting the nodes of the tree
        for l in data['links']:
            input = None
            output = None
            for i in nodes[l['to_node']].inputs:
                if i.identifier == l['to_socket']:
                    input = i
            for o in nodes[l['from_node']].outputs:
                if o.identifier == l['from_socket']:
                    output = o
            if input is not None and output is not None:
                node_tree.links.new(input, output)
            else:
                print('error at ', l['from_node'], ' ', l['from_socket'], '->', l['to_node'], ' ', l['to_socket'])

        # assigning the node tree to all nodes that had the old version of it
        for node in node_groups:
            node.node_tree = bpy.data.node_groups[name]