def migrate(cr, version):
    """Inventory sync is now export-only (Odoo is the source of truth).

    Convert any previous 'import' / 'both' direction to 'export'.
    """
    cr.execute(
        """
        UPDATE digitalnatie_woo_instance
           SET sync_inventory_direction = 'export'
         WHERE sync_inventory_direction IS NULL
            OR sync_inventory_direction NOT IN ('disabled', 'export')
        """
    )
