def migrate(cr, version):
    """Price sync is now export-only (Odoo is the source of truth).

    Convert any previous 'import' / 'both' direction to 'export'.
    """
    cr.execute(
        """
        UPDATE digitalnatie_woo_instance
           SET sync_price_direction = 'export'
         WHERE sync_price_direction IS NULL
            OR sync_price_direction NOT IN ('disabled', 'export')
        """
    )
