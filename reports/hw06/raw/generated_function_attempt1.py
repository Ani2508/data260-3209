from datetime import datetime, timedelta

def days_until_irb_review(due_date: str, today: str) -> int:
    """
    Calculate the number of days until the IRB continuing review is due.

    Args:
    - due_date (str): ISO date string (YYYY-MM-DD) of the IRB continuing review due date.
    - today (str): ISO date string (YYYY-MM-DD) of the current date.

    Returns:
    - int: The number of days from today until the IRB continuing review is due (negative if overdue).
    """
    try:
        due_date = datetime.fromisoformat(due_date)
        today = datetime.fromisoformat(today)
    except ValueError as e:
        raise ValueError("Invalid date format. Please use YYYY-MM-DD.") from e

    if due_date < today:
        raise ValueError("Due date is in the past.")

    return (due_date - today).days

# Test cases
import unittest

class TestDaysUntilIRBReview(unittest.TestCase):
    def test_due_date_today(self):
        due_date = "2024-03-16"
        today = "2024-03-16"
        self.assertEqual(days_until_irb_review(due_date, today), 0)

    def test_due_date_tomorrow(self):
        due_date = "2024-03-17"
        today = "2024-03-16"
        self.assertEqual(days_until_irb_review(due_date, today), 1)

    def test_due_date_yesterday(self):
        due_date = "2024-03-16"
        today = "2024-03-17"
        with self.assertRaises(ValueError):
            days_until_irb_review(due_date, today)

    def test_invalid_date_format(self):
        due_date = "2024/03/16"
        today = "2024-03-16"
        with self.assertRaises(ValueError):
            days_until_irb_review(due_date, today)

    def test_due_date_in_the_past(self):
        due_date = "2024-03-16"
        today = "2025-03-16"
        with self.assertRaises(ValueError):
            days_until_irb_review(due_date, today)

if __name__ == "__main__":
    unittest.main()
