from flask_wtf import FlaskForm
from wtforms.validators import InputRequired
from wtforms import StringField, SelectField

from planet.models.expression.networks import ExpressionNetworkMethod


class NeighborhoodToClustersForm(FlaskForm):
    network_id = SelectField('Network', coerce=int)
    description = StringField('Description', [InputRequired()])

    def populate_networks(self):
        self.network_id.choices = [(e.id, str(e))
                                   for e in ExpressionNetworkMethod.query.all()]
