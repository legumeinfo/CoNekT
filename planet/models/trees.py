from planet import db
from planet.models.sequences import Sequence
from planet.models.clades import Clade
from planet.models.relationships.sequence_sequence_clade import SequenceSequenceCladeAssociation

import utils.phylo as phylo

from yattag import Doc, indent
import newick
import json

SQL_COLLATION = 'NOCASE' if db.engine.name == 'sqlite' else ''


class TreeMethod(db.Model):
    __tablename__ = 'tree_methods'
    id = db.Column(db.Integer, primary_key=True)

    description = db.Column(db.Text)

    gene_family_method_id = db.Column(db.Integer,
                                      db.ForeignKey('gene_family_methods.id', ondelete='CASCADE'), index=True)

    trees = db.relationship('Tree',
                            backref=db.backref('method', lazy='joined'),
                            lazy='dynamic',
                            passive_deletes=True)

    def reconcile_trees(self):
        # Fetch required data from the database
        sequences = Sequence.query.all()
        clades = Clade.query.all()

        seq_to_species = {s.name: s.species.code for s in sequences}
        seq_to_id = {s.name: s.id for s in sequences}
        clade_to_species = {c.name: json.loads(c.species) for c in clades}
        clade_to_id = {c.name: c.id for c in clades}

        new_associations = []

        for t in self.trees:
            # Load tree from Newick string and start reconciliating
            tree = newick.loads(t.data_newick)[0]

            for node in tree.walk():
                if len(node.descendants) != 2:
                    if not node.is_binary:
                        # Print warning in case there is a non-binary node
                        print("[%d, %s] Skipping node... Can only reconcile binary nodes ..." % (tree.id, tree.label))
                    # Otherwise it is a leaf node and can be skipped
                    continue

                branch_one_seq = [l.name for l in node.descendants[0].get_leaves()]
                branch_two_seq = [l.name for l in node.descendants[1].get_leaves()]

                branch_one_species = set([seq_to_species[s] for s in branch_one_seq if s in seq_to_species.keys()])
                branch_two_species = set([seq_to_species[s] for s in branch_two_seq if s in seq_to_species.keys()])

                all_species = branch_one_species.union(branch_two_species)

                clade, _ = phylo.get_clade(all_species, clade_to_species)
                duplication = phylo.is_duplication(branch_one_species, branch_two_species, clade_to_species)

                duplication_consistency = None
                if duplication:
                    duplication_consistency = phylo.duplication_consistency(branch_one_species, branch_two_species)

                if clade is not None:
                    for seq_one in branch_one_seq:
                        for seq_two in branch_two_seq:
                            new_associations.append({
                                'sequence_one_id': seq_to_id[seq_one],
                                'sequence_two_id': seq_to_id[seq_two],
                                'tree_id': t.id,
                                'clade_id': clade_to_id[clade],
                                'duplication': 1 if duplication else 0,
                                'duplication_consistency_score': duplication_consistency
                            })
                            new_associations.append({
                                'sequence_one_id': seq_to_id[seq_two],
                                'sequence_two_id': seq_to_id[seq_one],
                                'tree_id': t.id,
                                'clade_id': clade_to_id[clade],
                                'duplication': 1 if duplication else 0,
                                'duplication_consistency_score': duplication_consistency
                            })

            if len(new_associations) > 400:
                db.engine.execute(SequenceSequenceCladeAssociation.__table__.insert(), new_associations)
                new_associations = []

        db.engine.execute(SequenceSequenceCladeAssociation.__table__.insert(), new_associations)


class Tree(db.Model):
    __tablename__ = 'trees'
    id = db.Column(db.Integer, primary_key=True)

    label = db.Column(db.String(50, collation=SQL_COLLATION), index=True)
    data_newick = db.Column(db.Text)
    data_phyloxml = db.Column(db.Text)

    gf_id = db.Column(db.Integer, db.ForeignKey('gene_families.id', ondelete='CASCADE'), index=True)
    method_id = db.Column(db.Integer, db.ForeignKey('tree_methods.id', ondelete='CASCADE'), index=True)

    @property
    def ascii_art(self):
        """
        Returns an ascii representation of the tree. Useful for quick visualizations

        :return: string with ascii representation of the tree
        """
        tree = newick.loads(self.data_newick)[0]

        return tree.ascii_art()

    @staticmethod
    def __yattag_node(node, tag, text, line, depth=0):
        with tag('clade'):
            if node.is_leaf:
                with tag('sequence'):
                    line('name', node.name)
            else:
                for d in node.descendants:
                    Tree.__yattag_node(d, tag, text, line, depth=depth + 1)

    @property
    def phyxml_test(self):
        """
        Function to test newick to phyxml conversion. (needs to be integrated with tree reconciliation so node
        annotation can be preserved)

        :return:
        """
        tree = newick.loads(self.data_newick)[0]

        doc, tag, text, line = Doc().ttl()

        with tag('phylogeny', rooted="True"):
            line('name', self.label)
            line('description', "PlaNet 2.0 PhyloXML tree")
            Tree.__yattag_node(tree, tag, text, line, depth=0)

        return indent(doc.getvalue())

    @property
    def count(self):
        tree = newick.loads(self.data_newick)[0]
        return len(tree.get_leaves())

    @property
    def sequences(self):
        tree = newick.loads(self.data_newick)[0]
        sequences = [l.name for l in tree.get_leaves()]

        return Sequence.query.filter(Sequence.name.in_(sequences))

    @property
    def tree_stripped(self):
        tree = newick.loads(self.data_newick)[0]
        tree.remove_lengths()

        print(newick.dumps([tree]))

        return newick.dumps([tree])
