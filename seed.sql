-- Apply only to a local demo database after Alembic upgrade head.
BEGIN;

-- Serialize seed runs and inserts into rooms without adding a unique constraint.
LOCK TABLE rooms IN SHARE ROW EXCLUSIVE MODE;

INSERT INTO rooms (name, description, category, capacity, nightly_rate, amenities)
SELECT demo.name, demo.description, demo.category, demo.capacity, demo.nightly_rate, demo.amenities
FROM (
    VALUES
        ('Standard Twin (Demo)', 'Two single beds', 'standard', 2, 25000.50, ARRAY['Wi-Fi']),
        ('Family Room (Demo)', 'One double bed and two single beds', 'family', 4, 42000.00,
            ARRAY['Wi-Fi', 'Air conditioning'])
) AS demo(name, description, category, capacity, nightly_rate, amenities)
WHERE NOT EXISTS (SELECT 1 FROM rooms WHERE rooms.name = demo.name)
ORDER BY demo.capacity, demo.name;

COMMIT;
