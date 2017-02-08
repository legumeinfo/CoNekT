from copy import deepcopy

from flask import url_for
from sqlalchemy.orm import joinedload

from planet.models.expression.specificity import ExpressionSpecificity
from planet.models.expression.profiles import ExpressionProfile
from planet.models.relationships import SequenceCoexpressionClusterAssociation
from planet.models.relationships import SequenceFamilyAssociation, SequenceInterproAssociation
from planet.models.sequences import Sequence
from planet.models.species import Species
from utils.color import family_to_shape_and_color


class CytoscapeHelper:

    @staticmethod
    def parse_network(network):
        """
        Parses a network generated by the ExpressionNetwork and CoexpressionCluster model, adding basic information
        and exporting the whole thing to a cytoscape.js compatible

        :param network: internal id of the network
        :return: Network fully compatible with Cytoscape.js
        """
        output = {"nodes": [], "edges": []}

        for n in network["nodes"]:
            output["nodes"].append({"data": n})

        for e in network["edges"]:
            output["edges"].append({"data": e})

        # add basic colors and shapes to nodes and url to gene pages

        for n in output["nodes"]:
            if n["data"]["gene_id"] is not None:
                n["data"]["gene_link"] = url_for("sequence.sequence_view", sequence_id=n["data"]["gene_id"])

            if n["data"]["id"] != n["data"]["gene_name"]:
                n["data"]["profile_link"] = url_for("expression_profile.expression_profile_find", probe=n["data"]["id"])

            n["data"]["color"] = "#CCC"
            n["data"]["shape"] = "ellipse"

        for e in output["edges"]:
            e["data"]["color"] = "#888"

        return output

    @staticmethod
    def add_family_data_nodes(network, family_method_id):
        """
        Adds family, clade and interpro information to a a cytoscape compatible network (dict)

        :param network: dict containing the network
        :param family_method_id: desired type/method used to construct the families

        :return: Cytoscape.js compatible network with family, clade and interpro information included
        """
        completed_network = deepcopy(network)

        sequence_ids = []
        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                sequence_ids.append(node["data"]["gene_id"])

        sequence_families = SequenceFamilyAssociation.query.\
            filter(SequenceFamilyAssociation.sequence_id.in_(sequence_ids)).\
            options(joinedload('family.clade')).\
            filter(SequenceFamilyAssociation.family.has(method_id=family_method_id)).all()

        sequence_interpro = SequenceInterproAssociation.query.\
            filter(SequenceInterproAssociation.sequence_id.in_(sequence_ids)).all()

        data = {}

        for s in sequence_families:
            data[s.sequence_id] = {}
            data[s.sequence_id]["name"] = s.family.name
            data[s.sequence_id]["id"] = s.gene_family_id
            data[s.sequence_id]["url"] = url_for('family.family_view', family_id=s.gene_family_id)
            if s.family.clade is not None:
                data[s.sequence_id]["clade"] = s.family.clade.name
                data[s.sequence_id]["clade_count"] = s.family.clade.species_count
            else:
                data[s.sequence_id]["clade"] = "None"
                data[s.sequence_id]["clade_count"] = 0

        for i in sequence_interpro:
            if i.sequence_id not in data:
                data[i.sequence_id] = {}
                data[i.sequence_id]["name"] = None
                data[i.sequence_id]["id"] = None
                data[i.sequence_id]["url"] = None
                data[i.sequence_id]["clade"] = "None"
                data[i.sequence_id]["clade_count"] = 0

            if "interpro" in data[i.sequence_id]:
                data[i.sequence_id]["interpro"] += [i.domain.label]
            else:
                data[i.sequence_id]["interpro"] = [i.domain.label]

        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys() \
                    and node["data"]["gene_id"] in data.keys():
                if "interpro" in data[node["data"]["gene_id"]]:
                    node["data"]["interpro"] = data[node["data"]["gene_id"]]["interpro"]
                node["data"]["family_name"] = data[node["data"]["gene_id"]]["name"]
                node["data"]["family_id"] = data[node["data"]["gene_id"]]["id"]
                node["data"]["family_url"] = data[node["data"]["gene_id"]]["url"]
                node["data"]["family_clade"] = data[node["data"]["gene_id"]]["clade"]
                node["data"]["family_clade_count"] = data[node["data"]["gene_id"]]["clade_count"]
            else:
                node["data"]["family_name"] = None
                node["data"]["family_id"] = None
                node["data"]["family_url"] = None
                node["data"]["family_color"] = "#CCC"
                node["data"]["family_shape"] = "rectangle"
                node["data"]["family_clade"] = "None"
                node["data"]["family_clade_count"] = 1

        return completed_network

    @staticmethod
    def add_lc_data_nodes(network):
        """
        Colors a network based on family information and label co-occurrences.

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with colors and shapes based on gene families and label co-occurrances
        """
        completed_network = deepcopy(network)

        gene_family_only, gene_both = {}, {}
        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                fam_only, both = [], []
                if "family_name" in node["data"]:
                    fam_only += [node["data"]["family_name"]]
                    both += [node["data"]["family_name"]]
                if "interpro" in node["data"]:
                    both += node["data"]["interpro"]
                gene_family_only[node["data"]["gene_id"]] = set(fam_only)
                gene_both[node["data"]["gene_id"]] = set(both)

        fam_to_shape_and_color = family_to_shape_and_color(gene_family_only)
        both_to_shape_and_color = family_to_shape_and_color(gene_both)

        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                if node["data"]["gene_id"] in fam_to_shape_and_color:
                    node["data"]["family_color"] = fam_to_shape_and_color[node["data"]["gene_id"]][1]
                    node["data"]["family_shape"] = fam_to_shape_and_color[node["data"]["gene_id"]][0]
                if node["data"]["gene_id"] in both_to_shape_and_color:
                    node["data"]["lc_label"] = both_to_shape_and_color[node["data"]["gene_id"]][2]
                    node["data"]["lc_color"] = both_to_shape_and_color[node["data"]["gene_id"]][1]
                    node["data"]["lc_shape"] = both_to_shape_and_color[node["data"]["gene_id"]][0]

        return completed_network

    @staticmethod
    def add_descriptions_nodes(network):
        """
        Adds the description to nodes (if available) and alternative names (aka gene tokens) to a cytoscape.js network

        :param network: Cytoscape.js compatible network object
        :return: Network with descriptions and tokens added
        """
        completed_network = deepcopy(network)

        sequence_ids = []
        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                sequence_ids.append(node["data"]["gene_id"])

        sequences = Sequence.query.filter(Sequence.id.in_(sequence_ids)).all()

        descriptions = {s.id: s.description for s in sequences}
        tokens = {s.id: ", ".join([x.name for x in s.xrefs if x.platform == 'token']) for s in sequences}

        # Set empty tokens to None
        for k, v in tokens.items():
            if v == "":
                tokens[k] = None

        for node in completed_network["nodes"]:
            if "data" in node.keys() and "gene_id" in node["data"].keys():
                if node["data"]["gene_id"] in descriptions.keys():
                    node["data"]["description"] = descriptions[node["data"]["gene_id"]]
                else:
                    node["data"]["description"] = None

                if node["data"]["gene_id"] in tokens.keys():
                    node["data"]["tokens"] = tokens[node["data"]["gene_id"]]
                else:
                    node["data"]["tokens"] = None

        return completed_network

    @staticmethod
    def add_depth_data_nodes(network):
        """
        Colors a cytoscape compatible network (dict) based on edge depth

        This function is no longer used as it has been replaced by a mapper in the cycss

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with depth information for nodes added
        """
        colored_network = deepcopy(network)

        colors = ["#3CE500", "#B7D800", "#CB7300", "#BF0003"]

        for node in colored_network["nodes"]:
            if "data" in node.keys() and "depth" in node["data"].keys():
                node["data"]["depth_color"] = colors[node["data"]["depth"]]

        return colored_network

    @staticmethod
    def add_connection_data_nodes(network):
        """
        A data to cytoscape compatible network's nodes based on the number of edges that node possesses

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with connectivity information for nodes added
        """
        colored_network = deepcopy(network)

        for node in colored_network["nodes"]:
            if "data" in node.keys() and "id" in node["data"].keys():
                probe = node["data"]["id"]
                neighbors = 0
                for edge in colored_network["edges"]:
                    if "data" in edge.keys() and "source" in edge["data"].keys() and "target" in edge["data"].keys():
                        if probe == edge["data"]["source"] or probe == edge["data"]["target"]:
                            neighbors += 1

                node["data"]["neighbors"] = neighbors

        return colored_network

    @staticmethod
    def add_species_data_nodes(network):
        """
        Colors nodes in a cytoscape compatible network (dict) based on species

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with depth information for edges added
        """
        colors = {s.id: s.color for s in Species.query.all()}
        colored_network = deepcopy(network)

        for node in colored_network["nodes"]:
            if "data" in node.keys() and "species_id" in node["data"].keys():
                node["data"]["species_color"] = colors[node["data"]["species_id"]]

        return colored_network

    @staticmethod
    def add_cluster_data_nodes(network, cluster_method_id):
        """
        Adds co-expression cluster information to a cytoscape compatible network (dict)

        :param network: dict containing the network
        :param cluster_method_id: internal id for the clustering method to use
        :return: Network dict completed with cluster info
        """
        colored_network = deepcopy(network)

        probes = [node['data']['id'] for node in colored_network['nodes'] if 'id' in node['data']]

        sequence_cluster_ass = SequenceCoexpressionClusterAssociation.query.filter(SequenceCoexpressionClusterAssociation.probe.in_(probes))\
            .filter(SequenceCoexpressionClusterAssociation.coexpression_cluster.has(method_id=cluster_method_id)).all()

        data = {}
        for sca in sequence_cluster_ass:
            data[sca.probe] = {}
            data[sca.probe]['cluster_id'] = sca.coexpression_cluster_id
            data[sca.probe]['cluster_name'] = sca.coexpression_cluster.name

        color_shapes = family_to_shape_and_color({p: [v['cluster_name']] for p, v in data.items()})

        for node in colored_network["nodes"]:
            if node['data']['id'] in data.keys():
                node['data']['cluster_id'] = data[node['data']['id']]['cluster_id']
                node['data']['cluster_name'] = data[node['data']['id']]['cluster_name']
                node['data']['cluster_url'] = url_for('expression_cluster.expression_cluster_view', cluster_id=node['data']['cluster_id'])
                if node['data']['id'] in color_shapes.keys():
                    node['data']['cluster_color'] = color_shapes[node['data']['id']][1]
                    node['data']['cluster_shape'] = color_shapes[node['data']['id']][0]

        return colored_network

    @staticmethod
    def add_specificity_data_nodes(network, specificity_method_id):
        """
        Adds profile specificity information to a cytoscape compatible network (dict)

        :param network: dict containing the network
        :param specificity_method_id: specificity method which should be used
        :return: Network dict completed with cluster info
        """
        colored_network = deepcopy(network)

        probes = [node['data']['id'] for node in colored_network['nodes'] if 'id' in node['data']]

        spm = ExpressionSpecificity.query.filter(ExpressionSpecificity.method_id == specificity_method_id).filter(ExpressionSpecificity.profile.has(ExpressionProfile.probe.in_(probes))).all();

        data = {}

        for s in spm:
            if s.profile.probe in data.keys():
                if s.score > data[s.profile.probe]['score']:
                    data[s.profile.probe]['score'] = s.score
                    data[s.profile.probe]['condition'] = s.condition
            else:
                data[s.profile.probe] = {}
                data[s.profile.probe]['score'] = s.score
                data[s.profile.probe]['condition'] = s.condition

        color_shapes = family_to_shape_and_color({p: [v['condition']] for p, v in data.items()})

        for node in colored_network["nodes"]:
            if node['data']['id'] in data.keys():
                node['data']['spm_score'] = data[node['data']['id']]['score']
                node['data']['spm_condition'] = data[node['data']['id']]['condition']
                if node['data']['id'] in color_shapes.keys():
                    node['data']['spm_condition_color'] = color_shapes[node['data']['id']][1]
                    node['data']['spm_condition_shape'] = color_shapes[node['data']['id']][0]

        return colored_network

    @staticmethod
    def add_depth_data_edges(network):
        """
        Colors a cytoscape compatible network (dict) based on edge depth

        This function is no longer used as it has been replaced by a mapper in the cycss

        :param network: dict containing the network
        :return: Cytoscape.js compatible network with depth information for edges added
        """
        colored_network = deepcopy(network)

        colors = ["#3CE500", "#B7D800", "#CB7300", "#BF0003"]

        for edge in colored_network["edges"]:
            if "data" in edge.keys() and "depth" in edge["data"].keys():
                edge["data"]["depth_color"] = colors[edge["data"]["depth"]]

        return colored_network

    @staticmethod
    def merge_networks(network_one, network_two):
        """
        Function to merge two networks. A compound/parent node is created for each network and based on the family_id,
        edges between homologous/orthologous genes are added.

        Note that label co-occurrences need to be (re-)calculated on the merged network

        :param network_one: Dictionary (cytoscape.js structure) of the first network
        :param network_two: Dictionary (cytoscape.js structure) of the second network
        :return: Cytoscape.js compatible network with both networks merged and homologs/orthologs connected
        """
        nodes = []
        edges = network_one['edges'] + network_two['edges']

        nodes.append({"data": {"id": "compound_node_one", "compound": True, "color": "#BEF"}})
        nodes.append({"data": {"id": "compound_node_two", "compound": True, "color": "#BEF"}})

        for node in network_one["nodes"]:
            node["data"]["parent"] = "compound_node_one"
            nodes.append(node)

        for node in network_two["nodes"]:
            node["data"]["parent"] = "compound_node_two"
            nodes.append(node)

        # draw edges between nodes from different networks
        # TODO: optimize this to avoid nested loop
        for node_one in network_one["nodes"]:
            for node_two in network_two["nodes"]:
                # if nodes are from the same family add an edge between them
                if node_one["data"]["family_id"] is not None \
                        and node_one["data"]["family_id"] == node_two["data"]["family_id"]:
                    edges.append({'data': {'source': node_one["data"]["id"],
                                           'target': node_two["data"]["id"],
                                           'color': "#33D",
                                           'homology': True}})

        return {'nodes': nodes, 'edges': edges}

    @staticmethod
    def get_families(network):
        """
        Extracts gene families from a cytoscape.js compatible network object

        :param network: network to extract families from
        :return: List of all families that occur in the network
        """
        return [f["data"]["family_name"] for f in network["nodes"] if 'data' in f.keys() and
                'family_name' in f["data"].keys() and
                f["data"]["family_name"] is not None]
