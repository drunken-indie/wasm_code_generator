
#Importing stuff
# In[1]:


import nbimporter; nbimporter.options["only_defs"] = False
from P0 import compileString
from ST import printSymTab

def runpywasm(wasmfile):
    import pywasm
    def write(i): print(i)
    def writeln(): print('\n')
    def read(): return int(input())
    vm = pywasm.load(wasmfile, {'P0lib': {'write': write, 'writeln': writeln, 'read': read}})


# In[2]:

##testing basic for each loop 
import P0, SC

P0.compileString("""
program p;
  var x: integer;
  begin
    for x in [1, 3, 5, 7, 5, 2] do                  {writes 1,3,5}
      begin write(x) end;
    writeln()             {writes }
  end
""",'fortest1.wat', target = 'wat')


# In[3]:


get_ipython().system('wat2wasm fortest1.wat')


# In[4]:


runpywasm('fortest1.wasm')


# In[5]:

##testing for each loop with inner for each loop
import P0, SC

P0.compileString("""
program p;
  var x, y: integer;
  begin
    for y in [1, 3, 5] do  
        begin 
        for x in [2, 4, 6] do
            begin write(x + y) end;         {writes 3, 5, 7, 5, 7, 9, 7, 9, 11}
      write(y) end;      {writes 1, 3, 5}  
    writeln()             {writes }
  end
""", 'fortest2.wat', target = 'wat')


# In[6]:


get_ipython().system('wat2wasm fortest2.wat')


# In[7]:


runpywasm('fortest2.wasm')


# In[8]:

##testing for each loop with procedure
import P0, SC

P0.compileString("""
program p;
  var x : integer;
  procedure q(v: integer);
    begin 
        write(v)       {writes 1,3,5}
    end;
    begin
        for x in [1, 3, 5] do
            begin q(x) end;
        writeln()
    end
""", 'fortest3.wat', target = 'wat')


# In[9]:


get_ipython().system('wat2wasm fortest3.wat')


# In[10]:


runpywasm('fortest3.wasm')


# In[11]:

##testing for loop
import P0, SC

P0.compileString("""
program p;
  var x: integer;
  begin
    for x := 3 to 8 do                  {writes 3, 4, 5, 6, 7, 8}
      begin write(x) end;
    writeln()             {writes }
  end
""",'fortest4.wat', target = 'wat')


# In[12]:


get_ipython().system('wat2wasm fortest4.wat')


# In[13]:


runpywasm('fortest4.wasm')


# In[14]:

##testing for loop with for each loop
import P0, SC

P0.compileString("""
program p;
  var x, y: integer;
  begin
    for y in [1, 3, 5] do  
        begin 
        for x := 8 downto 6 do
            begin write(x + y) end;         {writes 9, 8, 7, 11, 10, 9, 13, 12, 11}
      write(y) end;      {writes 1, 3, 5}  
    writeln()             {writes }
  end
""", 'fortest5.wat', target = 'wat')


# In[15]:


get_ipython().system('wat2wasm fortest5.wat')


# In[16]:


runpywasm('fortest5.wasm')


# In[17]:

##testing for loop with for each loop and procedure
import P0, SC

P0.compileString("""
program p;
  var x, y : integer;
  procedure q(v: integer);
    begin 
        write(v)       {writes 9, 8, 7, 11, 10, 9, 13, 12, 11}
    end;
    begin
        for x in [1, 3, 5] do
            begin
            for y := 8 downto 6 do
                begin q(x+y) end;  
            writeln() end;
        writeln()
    end
""", 'fortest6.wat', target = 'wat')


# In[18]:


get_ipython().system('wat2wasm fortest6.wat')


# In[19]:


runpywasm('fortest6.wasm')


# In[20]:

##testing case statement
import P0, SC

P0.compileString("""
program p;
  var x, y: integer;
  begin
    x := 7;
    case x of 3,5 : begin write(x) end; 2,4 : begin write(x) end else begin write(x+2); end ; end  {writes 9}
  end
""", 'casetest1.wat', target = 'wat')


# In[21]:


get_ipython().system('wat2wasm casetest1.wat')


# In[22]:


runpywasm('casetest1.wasm')


# In[23]:

##testing cast statement with for each loop
import P0, SC

P0.compileString("""
program p;
  var x, y: integer;
  var z : boolean;
  begin
    for x in [1, 3, 5] do 
        begin
        z := x > 0;
        case z of true : begin write(x) end; false : begin write(x) end else begin write(x+2); end ; end; {write 1, 3, 5}
        end;
      begin writeln() end;
    writeln()             {writes }
  end
""", 'casetest2.wat',target = 'wat')


# In[24]:


get_ipython().system('wat2wasm casetest2.wat')


# In[25]:


runpywasm('casetest2.wasm')


# In[26]:

##testing test case with for each loop and procedures
import P0, SC

P0.compileString("""
program p;
  var x : integer;
  var z : boolean;
  procedure a(v: integer);
    begin 
        write(v)       {writes 3}
    end;
  procedure b(w: integer);
    begin 
        write(w+5)       {writes 6, 10}
    end;  
    
    begin
        for x in [1, 3, 5] do 
           begin
             z := x = 3;
             case z of true : begin a(x) end; false : begin b(x) end else begin a(x+2); end ; end; {write 1, 3, 5}
           end;
        begin writeln() end;
    end
""", 'casetest3.wat', target = 'wat')


# In[27]:


get_ipython().system('wat2wasm casetest3.wat')


# In[28]:


runpywasm('casetest3.wasm')

