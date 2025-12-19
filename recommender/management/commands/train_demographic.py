from django.core.management.base import BaseCommand
from recommender.demographic_trainer import train_demographic_model
from recommender.services.populate_demographic import populate_demographic_recommendations


class Command(BaseCommand):
    help = "Train demographic model + populate recommendations"

    def handle(self, *args, **kwargs):

        print("📘 Training demographic model...")
        ok = train_demographic_model()

        if not ok:
            print("❌ Training failed (no data).")
            return

        print("✅ Training complete.")
        print("📘 Populating recommendations...")

        populate_demographic_recommendations()

        print("🎉 Done: Demographic recommendations populated!")
