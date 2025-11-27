from tortoise import fields, models

class City(models.Model):
    name = fields.CharField(max_length=200)
    timezone = fields.CharField(max_length=50, null=True)
    country_code = fields.CharField(max_length=2, null=True)
    population = fields.IntField(null=True)
    latitude = fields.FloatField()
    longitude = fields.FloatField()

    class Meta:
        table = "cities"
        indexes = [
            models.Index(fields=["name"], name="idx_city_name"),
        ]