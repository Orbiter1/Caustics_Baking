import bpy
import json


def export_node_group_to_json(name):
    if bpy.data.node_groups.find(name) == -1:
        return -1

    nodeTree = bpy.data.node_groups[name]
    nodeGroup = {
        'type': nodeTree.type,
        'outputs': [],
        'inputs': [],
        'nodes': [],
        'links': []
    }

    for o in nodeTree.outputs:
        nodeGroup['outputs'].append({'name': str(o.name), 'type': str(o.bl_socket_idname)})

    for i in nodeTree.inputs:
        input = {
            'name': i.name,
            'type': i.bl_socket_idname,
            'hide_value': i.hide_value
        }
        match i.bl_socket_idname:
            case 'NodeSocketFloat':
                input['default_value'] = i.default_value
                input['min_value'] = i.min_value
                input['max_value'] = i.max_value
                if nodeTree.type == 'GEOMETRY':
                    input['default_attribute_name'] = i.default_attribute_name
            case 'NodeSocketVector':
                input['default_value'] = (i.default_value[0], i.default_value[1], i.default_value[2])
                input['min_value'] = i.min_value
                input['max_value'] = i.max_value
                if nodeTree.type == 'GEOMETRY':
                    input['default_attribute_name'] = i.default_attribute_name
            case 'NodeSocketColor':
                input['default_value'] = (
                    i.default_value[0], i.default_value[1], i.default_value[2], i.default_value[3])
                if nodeTree.type == 'GEOMETRY':
                    input['default_attribute_name'] = i.default_attribute_name
        nodeGroup['inputs'].append(input)

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


def import_node_group_from_json(name, data):
    if data.replace(" ", "") != str(export_node_group_to_json(name)).replace(" ", ""):
        # Save all nodeGroups with this Nodetree for reassignment
        nodeGroups = []
        for nodeGroup in bpy.data.node_groups:
            for node in nodeGroup.nodes:
                if str(node.__class__.__name__) == 'ShaderNodeGroup':
                    if node.node_tree.name == name:
                        nodeGroups.append(node)
        for material in bpy.data.materials:
            if material.node_tree is not None:
                for node in material.node_tree.nodes:
                    if str(node.__class__.__name__) == 'ShaderNodeGroup':
                        if node.node_tree.name == name:
                            nodeGroups.append(node)

        data = json.loads(data)
        if bpy.data.node_groups.__contains__(name):
            bpy.data.node_groups.remove(bpy.data.node_groups[name])
        match data['type']:
            case 'SHADER':
                nodeTree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
            case 'GEOMETRY':
                nodeTree = bpy.data.node_groups.new(name, 'GeometryNodeTree')

        outputs = nodeTree.outputs
        outputs.clear()
        for o in data['outputs']:
            outputs.new(o['type'], o['name'])

        inputs = nodeTree.inputs
        inputs.clear()
        for i in data['inputs']:
            input = inputs.new(i['type'], i['name'])
            input.hide_value = i['hide_value']
            match i['type']:
                case 'NodeSocketFloat':
                    input.default_value = i['default_value']
                    input.min_value = i['min_value']
                    input.max_value = i['max_value']
                    if data['type'] == 'GEOMETRY':
                        input.default_attribute_name = i['default_attribute_name']
                case 'NodeSocketVector':
                    input.default_value = i['default_value']
                    input.min_value = i['min_value']
                    input.max_value = i['max_value']
                    if data['type'] == 'GEOMETRY':
                        input.default_attribute_name = i['default_attribute_name']
                case 'NodeSocketColor':
                    input.default_value = i['default_value']
                    if data['type'] == 'GEOMETRY':
                        input.default_attribute_name = i['default_attribute_name']

        nodes = nodeTree.nodes
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
                nodeTree.links.new(input, output)
            else:
                print('error at ', l['from_node'], ' ', l['from_socket'], '->', l['to_node'], ' ', l['to_socket'])

        for node in nodeGroups:
            node.node_tree = bpy.data.node_groups[name]
