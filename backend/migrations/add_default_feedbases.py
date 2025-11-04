"""
Migration: Add default system feedbases for all animal types

This migration:
1. Loads dairy and beef cattle feed data from CSV files
2. Creates system-level default feedbases accessible to all users
3. Creates placeholder feedbases for cat and dog (to be populated later)

System feedbases are stored in namespace: ("system_feedbases", animal_type, "default")
These are read-only and accessible to all users for formulation.
"""

import asyncio
import pandas as pd
from pathlib import Path
import logging
import sys
import os
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file from backend directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)
logger_setup = logging.getLogger(__name__)
logger_setup.info(f"Loaded environment from {env_path}")

from services.session_manager import session_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_csv_feedbase(csv_path: Path, animal_type: str) -> dict:
    """
    Load feed data from CSV file and convert to feedbase format.

    Supports two CSV formats:
    1. Cattle (dairy_cow, beef_cow): Uses CP_percent, EE_percent (all on DM basis)
    2. Companion animals (cat, dog): Uses CP_percent_DM, EE_percent_DM (explicit DM naming)

    Args:
        csv_path: Path to CSV file
        animal_type: Animal type (dairy_cow, beef_cow, cat, dog)

    Returns:
        Feedbase data dictionary with feeds
    """
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} feeds from {csv_path}")

        feedbase_data = {
            "animal_type": animal_type,
            "feeds": {}
        }

        for _, row in df.iterrows():
            feed_name = row['feed_name']

            # Extract base fields
            dm_percent = float(row['DM_percent'])
            cost_per_kg = 0.0  # Default cost, can be updated by users

            # Extract nutrients (all on DM basis)
            nutrients = {}

            # Handle both naming conventions for common nutrients
            # Cattle CSVs use: CP_percent, EE_percent, etc.
            # Cat/Dog CSVs use: CP_percent_DM, EE_percent_DM, etc.
            # Both are already on DM basis despite naming differences

            if 'CP_percent' in row and pd.notna(row['CP_percent']):
                nutrients['CP'] = float(row['CP_percent'])
            elif 'CP_percent_DM' in row and pd.notna(row['CP_percent_DM']):
                nutrients['CP'] = float(row['CP_percent_DM'])

            if 'EE_percent' in row and pd.notna(row['EE_percent']):
                nutrients['EE'] = float(row['EE_percent'])
            elif 'EE_percent_DM' in row and pd.notna(row['EE_percent_DM']):
                nutrients['EE'] = float(row['EE_percent_DM'])

            if 'NDF_percent' in row and pd.notna(row['NDF_percent']):
                nutrients['NDF'] = float(row['NDF_percent'])
            elif 'NDF_percent_DM' in row and pd.notna(row['NDF_percent_DM']):
                nutrients['NDF'] = float(row['NDF_percent_DM'])

            if 'ADF_percent' in row and pd.notna(row['ADF_percent']):
                nutrients['ADF'] = float(row['ADF_percent'])
            elif 'ADF_percent_DM' in row and pd.notna(row['ADF_percent_DM']):
                nutrients['ADF'] = float(row['ADF_percent_DM'])

            if 'NFE_percent' in row and pd.notna(row['NFE_percent']):
                nutrients['NFE'] = float(row['NFE_percent'])
            elif 'NFE_percent_DM' in row and pd.notna(row['NFE_percent_DM']):
                nutrients['NFE'] = float(row['NFE_percent_DM'])

            if 'Ash_percent' in row and pd.notna(row['Ash_percent']):
                nutrients['Ash'] = float(row['Ash_percent'])
            elif 'Ash_percent_DM' in row and pd.notna(row['Ash_percent_DM']):
                nutrients['Ash'] = float(row['Ash_percent_DM'])

            if 'Calcium_percent' in row and pd.notna(row['Calcium_percent']):
                nutrients['Ca'] = float(row['Calcium_percent'])
            elif 'Calcium_percent_DM' in row and pd.notna(row['Calcium_percent_DM']):
                nutrients['Ca'] = float(row['Calcium_percent_DM'])

            if 'Phosphorus_percent' in row and pd.notna(row['Phosphorus_percent']):
                nutrients['P'] = float(row['Phosphorus_percent'])
            elif 'Phosphorus_percent_DM' in row and pd.notna(row['Phosphorus_percent_DM']):
                nutrients['P'] = float(row['Phosphorus_percent_DM'])

            # Dairy-specific nutrients
            if animal_type == "dairy_cow":
                if 'MilkNetEnergy_Mcal_per_kg' in row and pd.notna(row['MilkNetEnergy_Mcal_per_kg']):
                    nutrients['NEL_Mcal'] = float(row['MilkNetEnergy_Mcal_per_kg'])
                if 'MilkNetEnergy_MJ_per_kg' in row and pd.notna(row['MilkNetEnergy_MJ_per_kg']):
                    nutrients['NEL_MJ'] = float(row['MilkNetEnergy_MJ_per_kg'])
                if 'NND_per_kg' in row and pd.notna(row['NND_per_kg']):
                    nutrients['NND'] = float(row['NND_per_kg'])
                if 'Digestible_CP_g_per_kg' in row and pd.notna(row['Digestible_CP_g_per_kg']):
                    nutrients['DCP'] = float(row['Digestible_CP_g_per_kg'])

            # Beef-specific nutrients
            elif animal_type == "beef_cow":
                if 'BeefMetabolizableEnergy_Mcal_per_kg' in row and pd.notna(row['BeefMetabolizableEnergy_Mcal_per_kg']):
                    nutrients['ME_Mcal'] = float(row['BeefMetabolizableEnergy_Mcal_per_kg'])
                if 'BeefMetabolizableEnergy_MJ_per_kg' in row and pd.notna(row['BeefMetabolizableEnergy_MJ_per_kg']):
                    nutrients['ME_MJ'] = float(row['BeefMetabolizableEnergy_MJ_per_kg'])
                if 'BeefMaintenanceNetEnergy_Mcal_per_kg' in row and pd.notna(row['BeefMaintenanceNetEnergy_Mcal_per_kg']):
                    nutrients['NEm_Mcal'] = float(row['BeefMaintenanceNetEnergy_Mcal_per_kg'])
                if 'BeefMaintenanceNetEnergy_MJ_per_kg' in row and pd.notna(row['BeefMaintenanceNetEnergy_MJ_per_kg']):
                    nutrients['NEm_MJ'] = float(row['BeefMaintenanceNetEnergy_MJ_per_kg'])
                if 'BeefGainNetEnergy_Mcal_per_kg' in row and pd.notna(row['BeefGainNetEnergy_Mcal_per_kg']):
                    nutrients['NEg_Mcal'] = float(row['BeefGainNetEnergy_Mcal_per_kg'])
                if 'BeefGainNetEnergy_MJ_per_kg' in row and pd.notna(row['BeefGainNetEnergy_MJ_per_kg']):
                    nutrients['NEg_MJ'] = float(row['BeefGainNetEnergy_MJ_per_kg'])
                if 'Digestible_CP_g_per_kg' in row and pd.notna(row['Digestible_CP_g_per_kg']):
                    nutrients['DCP'] = float(row['Digestible_CP_g_per_kg'])

                # Trace minerals (ppm)
                if 'Copper_ppm' in row and pd.notna(row['Copper_ppm']):
                    nutrients['Cu_ppm'] = float(row['Copper_ppm'])
                if 'Zinc_ppm' in row and pd.notna(row['Zinc_ppm']):
                    nutrients['Zn_ppm'] = float(row['Zinc_ppm'])
                if 'Manganese_ppm' in row and pd.notna(row['Manganese_ppm']):
                    nutrients['Mn_ppm'] = float(row['Manganese_ppm'])
                if 'Selenium_ppm' in row and pd.notna(row['Selenium_ppm']):
                    nutrients['Se_ppm'] = float(row['Selenium_ppm'])
                if 'Cobalt_ppm' in row and pd.notna(row['Cobalt_ppm']):
                    nutrients['Co_ppm'] = float(row['Cobalt_ppm'])
                if 'Iodine_ppm' in row and pd.notna(row['Iodine_ppm']):
                    nutrients['I_ppm'] = float(row['Iodine_ppm'])

            # Cat and Dog-specific nutrients
            elif animal_type in ["cat", "dog"]:
                # Metabolizable Energy (cat and dog use same column names)
                if 'CatME_kcal_per_kg_DM' in row and pd.notna(row['CatME_kcal_per_kg_DM']):
                    nutrients['ME_kcal'] = float(row['CatME_kcal_per_kg_DM'])
                elif 'DogME_kcal_per_kg_DM' in row and pd.notna(row['DogME_kcal_per_kg_DM']):
                    nutrients['ME_kcal'] = float(row['DogME_kcal_per_kg_DM'])

                if 'CatME_MJ_per_kg_DM' in row and pd.notna(row['CatME_MJ_per_kg_DM']):
                    nutrients['ME_MJ'] = float(row['CatME_MJ_per_kg_DM'])
                elif 'DogME_MJ_per_kg_DM' in row and pd.notna(row['DogME_MJ_per_kg_DM']):
                    nutrients['ME_MJ'] = float(row['DogME_MJ_per_kg_DM'])

                # Taurine (critical for cats, beneficial for dogs)
                if 'Taurine_percent_DM' in row and pd.notna(row['Taurine_percent_DM']):
                    nutrients['Taurine'] = float(row['Taurine_percent_DM'])

                # Crude protein in g/kg DM format (convert to %)
                if 'CrudeProtein_g_per_kg_DM' in row and pd.notna(row['CrudeProtein_g_per_kg_DM']):
                    nutrients['CP_g_kg'] = float(row['CrudeProtein_g_per_kg_DM'])

            # Create feed entry
            feedbase_data["feeds"][feed_name] = {
                "dm_percent": dm_percent,
                "nutrients": nutrients,
                "cost_per_kg": cost_per_kg
            }

        logger.info(f"Converted {len(feedbase_data['feeds'])} feeds for {animal_type}")
        return feedbase_data

    except Exception as e:
        logger.error(f"Error loading CSV {csv_path}: {e}")
        raise


async def create_placeholder_feedbase(animal_type: str) -> dict:
    """
    Create placeholder feedbase for animal types without data yet.

    Args:
        animal_type: Animal type (cat, dog)

    Returns:
        Empty feedbase data structure
    """
    return {
        "animal_type": animal_type,
        "feeds": {}
    }


async def run_migration():
    """
    Main migration function to create default system feedbases.
    """
    logger.info("Starting default feedbase migration...")

    # Get shared store instance
    from core.agent import _connection_manager
    store = await _connection_manager.get_shared_store()

    # Define data file paths (relative to project root)
    project_root = Path(__file__).parent.parent.parent.parent
    data_dir = project_root / "data"

    dairy_csv = data_dir / "feednutrientdairy_dataset_common.csv"
    beef_csv = data_dir / "feednutrientbeef_dataset_common.csv"
    cat_csv = data_dir / "cat_feed_dataset_common.csv"
    dog_csv = data_dir / "dog_feed_dataset_common.csv"

    # 1. Create dairy cow default feedbase
    if dairy_csv.exists():
        logger.info(f"Loading dairy cow feedbase from {dairy_csv}")
        dairy_feedbase = await load_csv_feedbase(dairy_csv, "dairy_cow")
        namespace = ("system_feedbases", "default_dairy_cow")
        await store.aput(namespace, "data", dairy_feedbase)
        logger.info(f"✓ Created default_dairy_cow feedbase with {len(dairy_feedbase['feeds'])} feeds")
    else:
        logger.warning(f"Dairy CSV not found at {dairy_csv}, skipping...")

    # 2. Create beef cow default feedbase
    if beef_csv.exists():
        logger.info(f"Loading beef cow feedbase from {beef_csv}")
        beef_feedbase = await load_csv_feedbase(beef_csv, "beef_cow")
        namespace = ("system_feedbases", "default_beef_cow")
        await store.aput(namespace, "data", beef_feedbase)
        logger.info(f"✓ Created default_beef_cow feedbase with {len(beef_feedbase['feeds'])} feeds")
    else:
        logger.warning(f"Beef CSV not found at {beef_csv}, skipping...")

    # 3. Create cat default feedbase
    if cat_csv.exists():
        logger.info(f"Loading cat feedbase from {cat_csv}")
        cat_feedbase = await load_csv_feedbase(cat_csv, "cat")
        namespace = ("system_feedbases", "default_cat")
        await store.aput(namespace, "data", cat_feedbase)
        logger.info(f"✓ Created default_cat feedbase with {len(cat_feedbase['feeds'])} feeds")
    else:
        logger.warning(f"Cat CSV not found at {cat_csv}, creating empty placeholder...")
        cat_feedbase = await create_placeholder_feedbase("cat")
        namespace = ("system_feedbases", "default_cat")
        await store.aput(namespace, "data", cat_feedbase)
        logger.info(f"✓ Created default_cat feedbase (empty placeholder)")

    # 4. Create dog default feedbase
    if dog_csv.exists():
        logger.info(f"Loading dog feedbase from {dog_csv}")
        dog_feedbase = await load_csv_feedbase(dog_csv, "dog")
        namespace = ("system_feedbases", "default_dog")
        await store.aput(namespace, "data", dog_feedbase)
        logger.info(f"✓ Created default_dog feedbase with {len(dog_feedbase['feeds'])} feeds")
    else:
        logger.warning(f"Dog CSV not found at {dog_csv}, creating empty placeholder...")
        dog_feedbase = await create_placeholder_feedbase("dog")
        namespace = ("system_feedbases", "default_dog")
        await store.aput(namespace, "data", dog_feedbase)
        logger.info(f"✓ Created default_dog feedbase (empty placeholder)")

    logger.info("Migration completed successfully!")
    logger.info("\nSummary:")
    logger.info(f"  - dairy_cow: {len(dairy_feedbase['feeds'])} feeds" if dairy_csv.exists() else "  - dairy_cow: Skipped (CSV not found)")
    logger.info(f"  - beef_cow: {len(beef_feedbase['feeds'])} feeds" if beef_csv.exists() else "  - beef_cow: Skipped (CSV not found)")
    logger.info(f"  - cat: {len(cat_feedbase['feeds'])} feeds" if cat_csv.exists() else "  - cat: Empty placeholder")
    logger.info(f"  - dog: {len(dog_feedbase['feeds'])} feeds" if dog_csv.exists() else "  - dog: Empty placeholder")


if __name__ == "__main__":
    asyncio.run(run_migration())
