"""Balance and payment tests with hand-computed amounts."""

from __future__ import annotations

from datetime import date

import pytest

from cekar.models import Split
from cekar.services import ServiceError, sync
from cekar.services import balances as bal
from cekar.services import expenses as ex
from cekar.services.balances import PaymentInput

DAY = date(2026, 3, 10)


def spend(session, payer, amount, split=Split.EQUAL, **kw):
    return ex.create_expense(
        session,
        payer.id,
        ex.ExpenseInput(
            title="Thing", amount_cents=amount, spent_on=DAY, payer_id=payer.id, split=split, **kw
        ),
    )


def pay(session, src, dst, amount):
    return bal.create_payment(session, src.id, PaymentInput(src.id, dst.id, amount, DAY))


def owes(session):
    return [(b.debtor_name, b.creditor_name, b.amount_cents) for b in bal.pair_balances(session)]


def test_empty(session, people):
    assert owes(session) == []
    assert bal.user_total(session, people.ana.id) == 0
    assert bal.expenses_version(session) == 0


def test_equal_odd_cents(session, two_people):
    ana, bor = two_people
    spend(session, ana, 1001)  # Ana 501, Bor 500
    assert owes(session) == [("Bor", "Ana", 500)]
    assert bal.user_total(session, ana.id) == 500
    assert bal.user_total(session, bor.id) == -500


def test_two_expenses_net_out(session, two_people):
    ana, bor = two_people
    spend(session, ana, 3000)  # Bor owes 1500
    spend(session, bor, 1000)  # Ana owes 500
    assert owes(session) == [("Bor", "Ana", 1000)]


def test_three_members_no_simplification(session, people):
    ana, bor, cene = people.ana, people.bor, people.cene
    spend(session, ana, 2000, Split.FOR_OTHER, for_user_id=bor.id)  # Bor owes Ana 2000
    spend(session, bor, 1000, Split.FOR_OTHER, for_user_id=cene.id)  # Cene owes Bor 1000
    spend(session, ana, 1000, Split.FOR_OTHER, for_user_id=bor.id)  # Bor owes Ana 3000 total
    assert owes(session) == [("Bor", "Ana", 3000), ("Cene", "Bor", 1000)]
    assert bal.user_total(session, bor.id) == -2000
    assert bal.user_total(session, cene.id) == -1000


def test_three_way_equal_with_odd_cents(session, people):
    spend(session, people.bor, 1000)  # Bor 334, Ana 333, Cene 333
    assert owes(session) == [("Ana", "Bor", 333), ("Cene", "Bor", 333)]


def test_exact_split(session, people):
    ana, bor, cene = people.ana, people.bor, people.cene
    spend(session, ana, 3000, Split.EXACT, exact_cents={ana.id: 500, bor.id: 1200, cene.id: 1300})
    assert owes(session) == [("Bor", "Ana", 1200), ("Cene", "Ana", 1300)]


def test_personal_changes_nothing(session, two_people):
    ana, _ = two_people
    spend(session, ana, 800, Split.PERSONAL)
    assert owes(session) == []
    assert bal.user_total(session, ana.id) == 0


def test_payments_partial_full_and_overpay(session, two_people):
    ana, bor = two_people
    spend(session, ana, 2000)  # Bor owes 1000
    p = pay(session, bor, ana, 400)
    assert owes(session) == [("Bor", "Ana", 600)]
    bal.update_payment(session, bor.id, p.id, PaymentInput(bor.id, ana.id, 600, DAY))
    assert owes(session) == [("Bor", "Ana", 400)]
    bal.update_payment(session, bor.id, p.id, PaymentInput(bor.id, ana.id, 1000, DAY))
    assert owes(session) == []
    assert bal.user_total(session, bor.id) == 0
    bal.update_payment(session, bor.id, p.id, PaymentInput(bor.id, ana.id, 1500, DAY))
    assert owes(session) == [("Ana", "Bor", 500)]


def test_overpay_warning(session, two_people):
    ana, bor = two_people
    spend(session, ana, 2000)
    ok = bal.check_payment(session, PaymentInput(bor.id, ana.id, 1000, DAY))
    assert ok == []
    warn = bal.check_payment(session, PaymentInput(bor.id, ana.id, 1500, DAY))
    assert [(w.key, w.params) for w in warn] == [
        ("warning.payment.overpay", {"owed_cents": 1000, "excess_cents": 500})
    ]
    # Opposite direction: Ana owes nothing.
    warn = bal.check_payment(session, PaymentInput(ana.id, bor.id, 100, DAY))
    assert warn[0].params == {"owed_cents": 0, "excess_cents": 100}


def test_overpay_warning_when_editing_ignores_own_amount(session, two_people):
    ana, bor = two_people
    spend(session, ana, 2000)
    p = pay(session, bor, ana, 1000)  # settled
    assert bal.check_payment(session, PaymentInput(bor.id, ana.id, 1000, DAY), payment_id=p.id) == []
    warn = bal.check_payment(session, PaymentInput(bor.id, ana.id, 1200, DAY), payment_id=p.id)
    assert warn[0].params == {"owed_cents": 1000, "excess_cents": 200}
    # Without the id the payment itself counts and the amount is all excess.
    warn = bal.check_payment(session, PaymentInput(bor.id, ana.id, 1000, DAY))
    assert warn[0].params == {"owed_cents": 0, "excess_cents": 1000}


def test_delete_and_restore_expense(session, two_people):
    ana, bor = two_people
    e = spend(session, ana, 3000)
    assert owes(session) == [("Bor", "Ana", 1500)]
    ex.delete_expense(session, ana.id, e.id)
    assert owes(session) == []
    ex.restore_expense(session, ana.id, e.id)
    assert owes(session) == [("Bor", "Ana", 1500)]


def test_delete_and_restore_payment(session, two_people):
    ana, bor = two_people
    spend(session, ana, 2000)
    p = pay(session, bor, ana, 1000)
    assert owes(session) == []
    deleted = bal.delete_payment(session, ana.id, p.id)
    assert deleted.deleted_at is not None
    assert owes(session) == [("Bor", "Ana", 1000)]
    with pytest.raises(ServiceError):
        bal.get_payment(session, p.id)
    bal.restore_payment(session, ana.id, p.id)
    assert owes(session) == []
    assert bal.get_payment(session, p.id).amount_cents == 1000
    with pytest.raises(ServiceError):
        bal.restore_payment(session, ana.id, p.id)


def test_payment_validation(session, two_people, add_user):
    ana, bor = two_people
    guest = add_user("Dana", member=False)
    for amount in (0, -1):
        with pytest.raises(ServiceError) as err:
            pay(session, bor, ana, amount)
        assert err.value.key == "error.amount.not_positive"
    with pytest.raises(ServiceError) as err:
        pay(session, ana, ana, 100)
    assert err.value.key == "error.payment.same_person"
    with pytest.raises(ServiceError) as err:
        bal.create_payment(session, ana.id, PaymentInput(ana.id, "nobody", 100, DAY))
    assert err.value.key == "error.not_found"
    with pytest.raises(ServiceError) as err:
        pay(session, guest, ana, 100)
    assert err.value.key == "error.payment.not_member"


def test_row_id_idempotent(session, two_people):
    ana, bor = two_people
    data = PaymentInput(bor.id, ana.id, 100, DAY)
    one = bal.create_payment(session, bor.id, data, row_id="p-1")
    two = bal.create_payment(session, bor.id, PaymentInput(bor.id, ana.id, 900, DAY), row_id="p-1")
    assert one is two and one.amount_cents == 100


def test_former_member_balance_stays_and_can_be_settled(session, people):
    ana, bor, cene = people.ana, people.bor, people.cene
    spend(session, ana, 2400, Split.FOR_OTHER, for_user_id=cene.id)
    cene.is_member = False
    sync.touch(cene, session)
    session.flush()
    assert owes(session) == [("Cene", "Ana", 2400)]
    assert bal.user_total(session, cene.id) == -2400
    p = pay(session, cene, ana, 1200)  # allowed: open balance
    assert owes(session) == [("Cene", "Ana", 1200)]
    # Editing the payment that nearly settled keeps working.
    bal.update_payment(session, ana.id, p.id, PaymentInput(cene.id, ana.id, 2400, DAY))
    assert owes(session) == []
    # No open balance left: a new payment with the former member is refused.
    with pytest.raises(ServiceError) as err:
        pay(session, cene, bor, 100)
    assert err.value.key == "error.payment.not_member"


def test_former_member_shares_still_count(session, people):
    ana, bor, cene = people.ana, people.bor, people.cene
    e = spend(session, ana, 1200)  # 400 each
    cene.is_member = False
    sync.touch(cene, session)
    assert owes(session) == [("Bor", "Ana", 400), ("Cene", "Ana", 400)]
    assert bor.is_member and e.id


def test_expenses_version_tracks_changes(session, two_people):
    ana, bor = two_people
    assert bal.expenses_version(session) == 0
    e = spend(session, ana, 1000)
    v1 = bal.expenses_version(session)
    assert v1 > 0
    ex.delete_expense(session, ana.id, e.id)
    v2 = bal.expenses_version(session)
    assert v2 > v1  # tombstones count
    p = pay(session, bor, ana, 100)
    v3 = bal.expenses_version(session)
    assert v3 > v2
    bal.delete_payment(session, ana.id, p.id)
    assert bal.expenses_version(session) > v3
