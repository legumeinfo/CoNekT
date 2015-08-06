from planet import db


class GeneFamilyMethod(db.Model):
    __tablename__ = 'gene_family_methods'
    id = db.Column(db.Integer, primary_key=True)
    method = db.Column(db.Text)

    families = db.relationship('GeneFamily', backref='method', lazy='dynamic')

    def __init__(self, method):
        self.method = method


class GeneFamily(db.Model):
    __tablename__ = 'gene_families'
    id = db.Column(db.Integer, primary_key=True)
    method_id = db.Column(db.Integer, db.ForeignKey('gene_family_methods.id'))
    name = db.Column(db.String(50), unique=True, index=True)

    def __init__(self, name):
        self.name = name
