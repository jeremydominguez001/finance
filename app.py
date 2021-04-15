import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# # Enable debugging
# app.config['DEBUG'] = True

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# API KEY pk_442a8be1ff3a49968997aea53453188c 

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # stocks = db.execute("SELECT * FROM transactions WHERE user_id = ?", session.get("user_id"))
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))

    # # Create a table that takes all the transactions and gets the portfolio's current value

    # db.execute("""CREATE TABLE portfolio (
    #                   stock_id INTEGER PRIMARY KEY,
    #                     symbol TEXT,
    #                 net_shares INTEGER,
    #                      price INTEGER,
    #                    user_id INTEGER,
    #                    FOREIGN KEY (user_id)
    #                 REFERENCES users(id))""")

    

    # If i had more time, I would definitely have this switch colors and update!
    # 👀 
    change = "bg-success"
    number_stocks = db.execute("SELECT * FROM transactions WHERE user_id = ? GROUP BY symbol", session.get("user_id"))
    # This hold value is where we will store the cumulative value of the porfolio
    hold_value = 0
    # This will be our tmp value for each security
    temp_value = 0
    # This will be our value for each share of stock the user owns
    net_shares = 0

    # Here we will esentially be finding all the stock trades the user made, group them by stock
    # Then sorting through each transaction of that stock to find their present holdings.
    for stock in number_stocks:
        number_transactions = db.execute("""SELECT * 
                                              FROM transactions
                                             WHERE symbol = UPPER(?)
                                               AND user_id = ?""", stock["symbol"], session.get("user_id"))
        for transaction in number_transactions:
            net_shares += transaction["shares"]
            temp_value += transaction["shares"] * transaction["price"]
        if temp_value > 0:
            stock_details = lookup(stock["symbol"])
            hold_value += temp_value
            db.execute("""INSERT INTO portfolio (symbol, net_shares, price) 
                          VALUES (UPPER(?), ?, ?)""", stock_details["symbol"], net_shares, stock_details["price"])

        temp_value = 0
        net_shares = 0
    
    # Now we store the user portfolio to get ready to upload to the html side
    user_portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", session.get("user_id"))
    
    acct_value = hold_value + cash[0]["cash"]

    return render_template("index.html", user_portfolio=user_portfolio, hold_value=usd(hold_value), buy_power=usd(cash[0]["cash"]), acct_value=usd(acct_value), change=change)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    
    if request.method == "POST":
        try:
            symbol = request.form.get("symbol")
            try:
                shares = int(request.form.get("shares"))
            except:
                return apology("Must provide number of shares")
            if not symbol:
                return apology("Must provide stock symbol")
            elif shares < 1:
                return apology("Must buy a share")
            quoted_dict = lookup(symbol)
            # We now find the total size of the purchase
            order_size = quoted_dict["price"] * shares
            # This was used to create the database 
            # db.execute("""CREATE TABLE transactions (
            #                       trans_id INTEGER PRIMARY KEY, 
            #                         symbol TEXT, 
            #                         shares INTEGER, 
            #                          price REAL, 
            #                        user_id INTEGER, 
            #                        FOREIGN KEY (user_id) 
            #                     REFERENCES users(id))""")
            
            # db.execute("""CREATE TABLE balance_changes (
            #              )""")           
                                          
            # Get the user's buying power
            acct_balance = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
            new_bal = acct_balance[0]["cash"] - quoted_dict["price"] * shares

            # We'll check the user's buying power.
            if new_bal > -1: 
                # Record the transaction
                # Here we update the user's account
                db.execute("""UPDATE users 
                                 SET cash = ? 
                               WHERE id = ?""", new_bal, session.get("user_id"))
                    
                db.execute("""INSERT INTO transactions (symbol, shares, price, user_id) 
                              VALUES (UPPER(?), ?, ?, ?)""", symbol, shares, float(quoted_dict["price"]), session.get("user_id"))

                return redirect("/")
            else: 
                return apology("Not enough buying power 😔")
        except:
            return apology("Not a valid symbol")
    else:
        return render_template("buy.html")

    


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Just a simple print of all the transactions we have saved
    transactions = db.execute("SELECT symbol, shares, price FROM transactions WHERE user_id = ?", session.get("user_id"))

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # We stay checking for post –– All day errday. 
    if request.method == "POST":
        try:
            symbol = request.form.get("symbol")
            # Check if anything is typed in the url
            if not symbol:
                return apology("Must provide quote")
            # We run it here again because I was receiving a type error when stored in a variable
            quoted_dict = lookup(symbol)
            return render_template("quoted.html", name=quoted_dict["name"], symbol=quoted_dict["symbol"], price=usd(quoted_dict["price"])) 
        except:
            return apology("Invalid quote")
    # If a GET request, we will simply just provide the quote page
    return render_template("quote.html")
        
@app.route("/addfunds", methods=["GET", "POST"])
@login_required
def addfunds():
    if request.method == "POST":
        amount = float(request.form.get("amount"))

        if not amount:
            return apology("Must provide an amount")
        elif amount < 1:
            return apology("Must provide a positive amount")

        # Get the user's current funds
        account = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
        
        # Apply these funds to the amount requested
        amount += account[0]["cash"]

        # Update the database
        db.execute("UPDATE users SET cash = ? WHERE id = ?", amount, session.get("user_id"))
        return redirect("/")
    else:
        return render_template("addfunds.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Clear any prior sessions
    session.clear()

    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    # Check if the user reached for the create account page with post
    if request.method == "POST":
        # Make sure that all field were filled
        if not username:
            return apology("Must provide username", 403)
        elif not password or not confirmation:
            return apology("Must provide password", 403)
        # If passwords don't match
        elif password != confirmation:
            return apology("Must provide matching confirmation password", 403)
        
        # TODO: If username already exists


        # Add password to database and the parenthesis get kinda scary... not going to lie 🤭
        db.execute("INSERT INTO users (username, hash, cash) VALUES(?, ?, 10000)", username, generate_password_hash(password))
        row = db.execute("SELECT * FROM users WHERE username = ?", username)
        
        # Remember which user has logged in
        session["user_id"] = row[0]["id"]

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        try:
            symbol = request.form.get("symbol")
            try:
                shares = int(request.form.get("shares"))
            except:
                return apology("Must provide number of shares")
            if not symbol:
                return apology("Must enter a stock symbol")
            elif shares < 1:
                return apology("Must enter a postive share amount")

            # Since the user will be selling shares, we will be applying negative shares
            shares = shares * -1
            stock = lookup(symbol)

            # Here we will check if the user actually owns the stock
            trades = db.execute("SELECT * FROM transactions WHERE symbol = UPPER(?)", symbol)

            # Here we have the user 
            user = db.execute("SELECT cash FROM users WHERE id = ?", session.get("user_id"))
            
            # Now we find the sum of their shares 
            total_shares = 0
            for trade in trades:
                total_shares += trade["shares"]
            if total_shares < shares * -1:
                return apology("Not enough shares to sell :(")
            else:
                db.execute("""UPDATE users
                                SET cash = ?
                            WHERE id = ?""", (shares * stock["price"] * -1) + float(user[0]["cash"]), session.get("user_id")) 
            
            # Here we will insert the order of the user 
            # Knowing that they have enough shares to make the trade
            db.execute("""INSERT INTO transactions (symbol, shares, price, user_id)
                          VALUES (UPPER(?), ?, ?, ?)""", symbol, shares, float(stock["price"]), session.get("user_id"))
            return redirect("/")
        except:
            return apology("Must enter a valid stock symbol")
    else:
        return render_template("sell.html")
        

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
