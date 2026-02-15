from fastapi import APIRouter, UploadFile, File
from typing import List
import pytesseract
from PIL import Image
import io
import re

router = APIRouter()

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from main import database


# -------------------------
# CATEGORY DETECTION
# -------------------------
def detect_category(text):
    text = text.lower()

    if any(word in text for word in ["restaurant", "food", "cafe", "dine"]):
        return "Food"
    elif any(word in text for word in ["uber", "ola", "rapido", "taxi"]):
        return "Transport"
    elif any(word in text for word in ["amazon", "flipkart", "myntra", "meesho"]):
        return "Shopping"
    elif any(word in text for word in ["electricity", "water", "gas"]):
        return "Utilities"
    else:
        return "Other"


# -------------------------
# CLEAN NUMBER FUNCTION
# -------------------------
def clean_number(num_str):
    num_str = num_str.replace(",", "")
    try:
        return float(num_str)
    except:
        return None


# -------------------------
# STRONG DATE EXTRACTION
# -------------------------
def extract_date(text):

    date_patterns = [
        r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",
        r"\b\d{4}[/-]\d{2}[/-]\d{2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{2}\s\d{4}\b",
        r"\b\d{2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{2}\s\d{4}\s\d{2}:\d{2}\s?(AM|PM)?\b"
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group()

    return "Not Found"


# -------------------------
# STRONG BILL TOTAL EXTRACTION
# -------------------------
def extract_bill_total(text):

    lines = text.split("\n")

    priority_keywords = [
        "bill total",
        "grand total",
        "amount payable",
        "amount due",
        "net payable",
        "total amount"
    ]

    # 1️⃣ Look for strong keywords
    for line in lines:
        lower_line = line.lower()

        if any(keyword in lower_line for keyword in priority_keywords):

            numbers = re.findall(r"\d[\d,]*\.?\d*", line)

            for num in reversed(numbers):
                value = clean_number(num)
                if value and value > 10:
                    return value

    # 2️⃣ General total (excluding subtotal)
    for line in lines:
        lower_line = line.lower()

        if "total" in lower_line and "sub" not in lower_line:

            numbers = re.findall(r"\d[\d,]*\.?\d*", line)

            for num in reversed(numbers):
                value = clean_number(num)
                if value and value > 10:
                    return value

    # 3️⃣ Fallback (ignore small values)
    all_numbers = re.findall(r"\d[\d,]*\.?\d*", text)

    valid_numbers = []

    for num in all_numbers:
        value = clean_number(num)
        if value and 10 <= value <= 50000:
            valid_numbers.append(value)

    if valid_numbers:
        return max(valid_numbers)

    return 0


# -------------------------
# STRONG SALARY EXTRACTION
# -------------------------
def extract_salary(text):

    lines = text.split("\n")

    salary_keywords = [
        "net salary",
        "net pay",
        "take home",
        "take-home",
        "gross salary",
        "gross pay",
        "salary credited",
        "amount credited"
    ]

    # 1️⃣ Priority keyword matching
    for line in lines:
        lower_line = line.lower()

        if any(keyword in lower_line for keyword in salary_keywords):

            numbers = re.findall(r"\d[\d,]*\.?\d*", line)

            for num in reversed(numbers):
                value = clean_number(num)
                if value and value > 1000:
                    return value

    # 2️⃣ Fallback: Largest realistic salary
    all_numbers = re.findall(r"\d[\d,]*\.?\d*", text)

    valid_numbers = []

    for num in all_numbers:
        value = clean_number(num)
        if value and 1000 <= value <= 10000000:
            valid_numbers.append(value)

    if valid_numbers:
        return max(valid_numbers)

    return 0


# -------------------------
# UPLOAD BILL
# -------------------------
@router.post("/upload-bill")
async def upload_bill(files: List[UploadFile] = File(...)):

    added_expenses = []

    for file in files:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        image = image.convert("RGB")
        extracted_text = pytesseract.image_to_string(image)

        total_amount = extract_bill_total(extracted_text)
        bill_date = extract_date(extracted_text)
        category = detect_category(extracted_text)

        database["expenses"].append({
            "amount": total_amount,
            "category": category,
            "date": bill_date,
            "description": file.filename
        })

        added_expenses.append({
            "amount": total_amount,
            "date": bill_date,
            "category": category
        })

    total_expense = sum(item["amount"] for item in database["expenses"])

    income_amount = 0
    if database["income"] is not None:
        income_amount = database["income"]["amount"]

    savings = income_amount - total_expense

    return {
        "new_expenses_added": added_expenses,
        "total_expense": total_expense,
        "income": income_amount,
        "savings": savings
    }


# -------------------------
# UPLOAD SALARY
# -------------------------
@router.post("/upload-salary")
async def upload_salary(file: UploadFile = File(...)):

    contents = await file.read()
    image = Image.open(io.BytesIO(contents))
    image = image.convert("RGB")
    extracted_text = pytesseract.image_to_string(image)

    estimated_salary = extract_salary(extracted_text)

    database["income"] = {
        "amount": estimated_salary,
        "source": "Salary Slip Upload"
    }

    total_expense = sum(item["amount"] for item in database["expenses"])
    savings = estimated_salary - total_expense

    return {
        "detected_income": estimated_salary,
        "total_expense": total_expense,
        "savings": savings
    }
