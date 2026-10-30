from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
import sqlite3
from datetime import datetime

ROOT = Path(__file__).parent
DB = ROOT / 'nexora.db'
app = FastAPI(title='Nexora V4')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT DEFAULT '', phone TEXT DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT DEFAULT '', price REAL NOT NULL CHECK(price>=0), stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0));
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT, quantity INTEGER NOT NULL CHECK(quantity>0), unit_price REAL NOT NULL, total REAL NOT NULL, status TEXT NOT NULL DEFAULT 'Pending', created_at TEXT NOT NULL);
        ''')
init()

class Customer(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = ''
    phone: str = ''
class Product(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = ''
    price: float = Field(ge=0)
    stock: int = Field(ge=0)
class Order(BaseModel):
    customer_id: int
    product_id: int
    quantity: int = Field(gt=0)
    status: str = 'Pending'
class Status(BaseModel):
    status: str

def rows(query, args=()):
    with connect() as c:
        return [dict(r) for r in c.execute(query, args).fetchall()]

def one(table, id):
    r=rows(f'SELECT * FROM {table} WHERE id=?',(id,))
    if not r: raise HTTPException(404, 'Record not found')
    return r[0]

@app.get('/')
def home(): return FileResponse(ROOT/'static'/'index.html')
@app.get('/api/customers')
def customers(): return rows('SELECT * FROM customers ORDER BY id DESC')
@app.post('/api/customers',status_code=201)
def add_customer(x:Customer):
    with connect() as c:
        id=c.execute('INSERT INTO customers(name,email,phone,created_at) VALUES(?,?,?,?)',(x.name.strip(),x.email,x.phone,datetime.now().isoformat(timespec='seconds'))).lastrowid
    return one('customers',id)
@app.put('/api/customers/{id}')
def edit_customer(id:int,x:Customer):
    one('customers',id)
    with connect() as c: c.execute('UPDATE customers SET name=?,email=?,phone=? WHERE id=?',(x.name.strip(),x.email,x.phone,id))
    return one('customers',id)
@app.delete('/api/customers/{id}')
def del_customer(id:int):
    one('customers',id)
    try:
        with connect() as c: c.execute('DELETE FROM customers WHERE id=?',(id,))
    except sqlite3.IntegrityError: raise HTTPException(409,'Customer has orders; cannot delete')
    return {'ok':True}
@app.get('/api/products')
def products(): return rows('SELECT * FROM products ORDER BY id DESC')
@app.post('/api/products',status_code=201)
def add_product(x:Product):
    with connect() as c: id=c.execute('INSERT INTO products(name,category,price,stock) VALUES(?,?,?,?)',(x.name.strip(),x.category,x.price,x.stock)).lastrowid
    return one('products',id)
@app.put('/api/products/{id}')
def edit_product(id:int,x:Product):
    one('products',id)
    with connect() as c: c.execute('UPDATE products SET name=?,category=?,price=?,stock=? WHERE id=?',(x.name.strip(),x.category,x.price,x.stock,id))
    return one('products',id)
@app.delete('/api/products/{id}')
def del_product(id:int):
    one('products',id)
    try:
        with connect() as c: c.execute('DELETE FROM products WHERE id=?',(id,))
    except sqlite3.IntegrityError: raise HTTPException(409,'Product has orders; cannot delete')
    return {'ok':True}
@app.get('/api/orders')
def orders(): return rows('''SELECT o.*,c.name customer_name,p.name product_name FROM orders o JOIN customers c ON c.id=o.customer_id JOIN products p ON p.id=o.product_id ORDER BY o.id DESC''')
@app.post('/api/orders',status_code=201)
def add_order(x:Order):
    if x.status not in ('Pending','Processing','Completed','Cancelled'): raise HTTPException(400,'Invalid status')
    one('customers',x.customer_id)
    p=one('products',x.product_id)
    with connect() as c:
        if x.status!='Cancelled':
            updated=c.execute('UPDATE products SET stock=stock-? WHERE id=? AND stock>=?',(x.quantity,x.product_id,x.quantity))
            if updated.rowcount==0: raise HTTPException(400,'Insufficient stock')
        id=c.execute('INSERT INTO orders(customer_id,product_id,quantity,unit_price,total,status,created_at) VALUES(?,?,?,?,?,?,?)',(x.customer_id,x.product_id,x.quantity,p['price'],round(p['price']*x.quantity,2),x.status,datetime.now().isoformat(timespec='seconds'))).lastrowid
    return rows('SELECT * FROM orders WHERE id=?',(id,))[0]
@app.patch('/api/orders/{id}')
def update_status(id:int,x:Status):
    if x.status not in ('Pending','Processing','Completed','Cancelled'): raise HTTPException(400,'Invalid status')
    o=one('orders',id)
    with connect() as c:
        if o['status']=='Cancelled' and x.status!='Cancelled':
            u=c.execute('UPDATE products SET stock=stock-? WHERE id=? AND stock>=?',(o['quantity'],o['product_id'],o['quantity']))
            if u.rowcount==0: raise HTTPException(400,'Insufficient stock to restore order')
        elif o['status']!='Cancelled' and x.status=='Cancelled':
            c.execute('UPDATE products SET stock=stock+? WHERE id=?',(o['quantity'],o['product_id']))
        c.execute('UPDATE orders SET status=? WHERE id=?',(x.status,id))
    return one('orders',id)
@app.get('/api/analytics')
def analytics():
    with connect() as c:
        total=c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status='Completed'").fetchone()[0]
        count=c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        customers=c.execute('SELECT COUNT(*) FROM customers').fetchone()[0]
        products=c.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        series=[dict(r) for r in c.execute("SELECT substr(created_at,1,10) day,round(SUM(total),2) revenue FROM orders WHERE status='Completed' GROUP BY day ORDER BY day DESC LIMIT 14")]
    return {'revenue':total,'orders':count,'customers':customers,'products':products,'series':list(reversed(series))}
