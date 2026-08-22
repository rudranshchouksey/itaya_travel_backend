async def test_get_user_bookings(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Create a booking
    await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )

    # Get user bookings
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings", headers=headers
    )
    assert res.status_code == 200
    assert len(res.json()) >= 1


async def test_get_booking_by_id(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Create a booking
    create_res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    b_id = create_res.json()["id"]

    # Get booking by id
    res = await async_client.get(
        f"{settings.API_V1_PREFIX}/bookings/{b_id}", headers=headers
    )
    assert res.status_code == 200
    assert res.json()["id"] == b_id


async def test_successful_experience_booking(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "experience",
                "experience_id": str(exp_id),
                "start_date": start_d.isoformat(),
                "start_time": "10:00:00",
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 201
    assert res.json()["total"] == "60.00"  # price_override was 60


async def test_unavailable_experience(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "experience",
                "experience_id": str(exp_id),
                "start_date": start_d.isoformat(),
                "start_time": "10:00:00",
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    # Book once
    await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )

    # Book again
    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 422
    assert "fully booked" in res.json()["error"]["message"].lower()


async def test_booking_multiple_items(async_client: AsyncClient, test_user_token: str, db_session: AsyncSession, test_user: User):
    headers = {"Authorization": f"Bearer {test_user_token}"}
    listing_id, exp_id = await setup_test_data(db_session, test_user)

    start_d = date.today() + timedelta(days=10)
    end_d = start_d + timedelta(days=2)

    booking_data = {
        "currency": "USD",
        "items": [
            {
                "item_type": "stay",
                "listing_id": str(listing_id),
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "quantity": 1,
                "guest_count": 2,
            },
            {
                "item_type": "experience",
                "experience_id": str(exp_id),
                "start_date": start_d.isoformat(),
                "start_time": "10:00:00",
                "quantity": 1,
                "guest_count": 2,
            }
        ],
        "guests": [{"first_name": "T", "last_name": "U", "is_primary": True}],
    }

    res = await async_client.post(
        f"{settings.API_V1_PREFIX}/bookings", json=booking_data, headers=headers
    )
    assert res.status_code == 201
    # total should be 2 days * 100 + 1 * 60 = 260.00
    assert res.json()["total"] == "260.00"
