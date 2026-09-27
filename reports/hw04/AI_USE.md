# AI_USE.md

## 1. What I used an AI assistant for, and what I did myself

I used Claude to help write the backend code (FastAPI routes, database models, login
sessions), the React frontend, the script that measures the N+1 problem, and the RAG
system (splitting documents into chunks, searching them, and writing the prompts for
the three setups). Claude also helped me fix bugs as they came up — a duplicate class
in models.py, a routing bug that caused a 405 error, an Ollama memory crash, and a
small React syntax error.

I did all the actual work myself. I ran every command, installed the packages, set up
MySQL, tested every API in Postman and in the browser, filled the database with test
data, ran the measurement and RAG scripts, and checked the real output at every step
before moving on.

## 2. One AI-produced output that was wrong or unsuitable

Claude first told me to put two debug routes (/api/debug/query-count and
/api/debug/reset-query-count) after the line app.mount("/", StaticFiles(...)) in
main.py. This broke the reset route — it gave a 405 Method Not Allowed error, because
the static file mount grabbed the request before it could reach my debug routes.

## 3. How I found the problem

I tested the reset route in FastAPI's /docs page and got a 405 error instead of the
200 I expected. I sent the error and my full main.py file back to Claude, and it
compared the order of my routes to how FastAPI checks them (top to bottom) and found
that the static file mount was catching the request first.

## 4. What I changed, and why it works now

I moved the two debug routes above the app.mount(...) line. FastAPI checks routes in
the order they're written, so putting the debug routes first means they get matched
before the static file mount can grab the request. After moving them, both debug
routes worked and returned 200, which I checked again in PowerShell.