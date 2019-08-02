'''
The P0 Compiler
COMP SCI 4TB3/6TB3, McMaster University
Original Author: Emil Sekerinski, February 2017, updated February 2019
Modified by Rickesh Mistry, Ryan Ticlo, Minsik Kim
This collection of jupyter notebooks develops a compiler for P0, a subset of Pascal. 
The compiler generates MIPS code, but is modularized to facilitate other targets. 
Pascal is a language that was designed with ease of compilation in mind; 
the MIPS architecture is representative of Reduced Instruction Set Computing (RISC) processors.
'''

'''
selector ::= {"." ident | "[" expression "]"}.
factor ::= ident selector | integer | "(" expression ")" | "not" factor.
term ::= factor {("*" | "div" | "mod" | "and") factor}.
simpleExpression ::= ["+" | "-"] term {("+" | "-" | "or") term}.
expression ::= simpleExpression
    {("=" | "<>" | "<" | "<=" | ">" | ">=") simpleExpression}.
compoundStatement = "begin" statement {";" statement} "end"
statement ::=
    ident selector ":=" expression |
    ident "(" [expression {"," expression}] ")" |
    compoundStatement |
    "if" expression "then" statement ["else"statement] |
    "while" expression "do" statement |
    ####"case" expression "of" case {";" case} [elsePart] [";"] "end" |
    ####"for" controlVariable ":=" initialValue ("to"|"downto") finalValue "do" statement |
    ####"for" controlVariable "in" "[" constList "]" "do" statement
####case :: = constList ":" statement
####elsePart ::= ("else"|"otherwise") statementlist
####constList ::= expression {“,” expression}
####statementlist ::= statement {";" statement}
####controlVariable ::= ident
####initialValue ::= expression
####finalValue ::= expression
type ::=
    ident |
    "array" "[" expression ".." expression "]" "of" type |
    "record" typedIds {";" typedIds} "end".
typedIds ::= ident {"," ident} ":" type.
declarations ::=
    {"const" ident "=" expression ";"}
    {"type" ident "=" type ";"}
    {"var" typedIds ";"}
    {"procedure" ident ["(" [["var"] typedIds {";" ["var"] typedIds}] ")"] ";"
        declarations compoundStatement ";"}.
program ::= "program" ident ";" declarations compoundStatement.


'''
#The scanner and symbol table are always imported. Depending on the selected target,
# a different code generator is imported when compilation starts.
import nbimporter
nbimporter.options["only_defs"] = False
import SC  #  used for SC.init, SC.sym, SC.val, SC.error
from SC import TIMES, DIV, MOD, AND, PLUS, MINUS, OR, EQ, NE, LT, GT, \
    LE, GE, PERIOD, COMMA, COLON, RPAREN, RBRAK, OF, THEN, DO, LPAREN, \
    LBRAK, NOT, BECOMES, NUMBER, IDENT, SEMICOLON, END, ELSE, IF, WHILE, \
    ARRAY, RECORD, CONST, TYPE, VAR, PROCEDURE, BEGIN, PROGRAM, EOF, \
    getSym, mark, TILDE, AMP, BAR, FOR, IN, TO, DOWNTO, CASE, OTHERWISE
import ST  #  used for ST.init
from ST import Var, Ref, Const, Type, Proc, StdProc, Int, Bool, Enum, \
    Record, Array, newDecl, find, openScope, topScope, closeScope, printSymTab

#The first and follow sets for recursive descent parsing.
FIRSTFACTOR = {IDENT, NUMBER, LPAREN, NOT, TILDE}
FOLLOWFACTOR = {TIMES, DIV, MOD, AND, OR, PLUS, MINUS, EQ, NE, LT, LE, GT, GE,
                COMMA, SEMICOLON, THEN, ELSE, RPAREN, RBRAK, DO, PERIOD, END, AMP, BAR, IN}
FIRSTEXPRESSION = {PLUS, MINUS, IDENT, NUMBER, LPAREN, NOT, TILDE}
FIRSTSTATEMENT = {IDENT, IF, WHILE, BEGIN, FOR, CASE}
FOLLOWSTATEMENT = {SEMICOLON, END, ELSE, IN, BECOMES}
FIRSTTYPE = {IDENT, RECORD, ARRAY, LPAREN}
FOLLOWTYPE = {SEMICOLON}
FIRSTDECL = {CONST, TYPE, VAR, PROCEDURE}
FOLLOWDECL = {BEGIN}
FOLLOWPROCCALL = {SEMICOLON, END, ELSE}
STRONGSYMS = {CONST, TYPE, VAR, PROCEDURE, WHILE, IF, BEGIN, EOF}


#Procedure selector(x) parses
#	selector ::= {"." ident | "[" expression "]"}.

def selector(x):
    while SC.sym in {PERIOD, LBRAK}:
        if SC.sym == PERIOD:  #  x.f
            getSym()
            if SC.sym == IDENT:
                if type(x.tp) == Record:
                    for f in x.tp.fields:
                        if f.name == SC.val:
                            x = CG.genSelect(x, f); break
                    else: mark("not a field")
                    getSym()
                else: mark("not a record")
            else: mark("identifier expected")
        else:  #  x[y]
            getSym(); y = expression()
            if type(x.tp) == Array:
                if y.tp == Int:
                    if type(y) == Const and \
                       (y.val < x.tp.lower or y.val >= x.tp.lower + x.tp.length):
                        mark('index out of bounds')
                    else: x = CG.genIndex(x, y)
                else: mark('index not integer')
            else: mark('not an array')
            if SC.sym == RBRAK: getSym()
            else: mark("] expected")
    return x


#Procedure factor() parses
#	factor ::= ident selector | integer | "(" expression ")" | "not" factor.

def factor():
    if SC.sym not in FIRSTFACTOR:
        mark("expression expected")
        while SC.sym not in FIRSTFACTOR | FOLLOWFACTOR | STRONGSYMS: getSym()
    if SC.sym == IDENT:
        x = find(SC.val)
        if type(x) in {Var, Ref}: x = CG.genVar(x); getSym()
        elif type(x) == Const: x = Const(x.tp, x.val); x = CG.genConst(x); getSym()
        else: mark('expression expected')
        x = selector(x)
    elif SC.sym == NUMBER:
        x = Const(Int, SC.val); x = CG.genConst(x); getSym()
    elif SC.sym == LPAREN:
        getSym(); x = expression()
        if SC.sym == RPAREN: getSym()
        else: mark(") expected")
    elif SC.sym == NOT:
        getSym(); x = factor()
        if x.tp != Bool: mark('not boolean')
        elif type(x) == Const: x.val = 1 - x.val # constant folding
        else: x = CG.genUnaryOp(NOT, x)
    elif SC.sym == TILDE:
        getSym(); x = factor()
        if x.tp != Int: mark('not integer')
        elif type(x)  == Const: x.val = ~x.val
        else: x = CG.genUnaryOp(TILDE, x)
    else: x = Const(None, 0)
    return x


#Procedure term() parses
#	term ::= factor {("*" | "div" | "mod" | "and") factor}.   

def term():
    x = factor()
    while SC.sym in {TIMES, DIV, MOD, AND, AMP}:
        op = SC.sym; getSym();
        if op == AND and type(x) != Const: x = CG.genUnaryOp(AND, x)
        y = factor() # x op y
        if x.tp == Int == y.tp and op in {TIMES, DIV, MOD, AMP}:
            if type(x) == Const == type(y): # constant folding
                if op == TIMES: x.val = x.val * y.val
                elif op == DIV: x.val = x.val // y.val
                elif op == MOD: x.val = x.val % y.val
                elif op == AMP: x.val = x.val & y.val
            else: x = CG.genBinaryOp(op, x, y)
        elif x.tp == Bool == y.tp and op == AND:
            if type(x) == Const: # constant folding
                if x.val: x = y # if x is true, take y, else x
            else: x = CG.genBinaryOp(AND, x, y)
        else: mark('bad type')
    return x


#Procedure simpleExpression() parses
#	simpleExpression ::= ["+" | "-"] term {("+" | "-" | "or") term}.    

def simpleExpression():
    if SC.sym == PLUS:
        getSym(); x = term()
    elif SC.sym == MINUS:
        getSym(); x = term()
        if x.tp != Int: mark('bad type')
        elif type(x) == Const: x.val = - x.val # constant folding
        else: x = CG.genUnaryOp(MINUS, x)
    else: x = term()
    while SC.sym in {PLUS, MINUS, OR, BAR}:
        op = SC.sym; getSym()
        if op == OR and type(x) != Const: x = CG.genUnaryOp(OR, x)
        y = term() # x op y
        if x.tp == Int == y.tp and op in {PLUS, MINUS, BAR}:
            if type(x) == Const == type(y): # constant folding
                if op == PLUS: x.val = x.val + y.val
                elif op == MINUS: x.val = x.val - y.val
                elif op == BAR: x.val = x.val | y.val
            else: x = CG.genBinaryOp(op, x, y)
        elif x.tp == Bool == y.tp and op == OR:
            if type(x) == Const: # constant folding
                if not x.val: x = y # if x is false, take y, else x
            else: x = CG.genBinaryOp(OR, x, y)
        else: mark('bad type')
    return x


#Procedure expression() parses
#	expression ::= simpleExpression
#             {("=" | "<>" | "<" | "<=" | ">" | ">=") simpleExpression}.   

def expression():
    x = simpleExpression()
    while SC.sym in {EQ, NE, LT, LE, GT, GE}:
        op = SC.sym; getSym(); y = simpleExpression() # x op y
        if x.tp == y.tp in (Int, Bool):
            if type(x) == Const == type(y): # constant folding
                if op == EQ: x.val = x.val == y.val
                elif op == NE: x.val = x.val != y.val
                elif op == LT: x.val = x.val < y.val
                elif op == LE: x.val = x.val <= y.val
                elif op == GT: x.val = x.val > y.val
                elif op == GE: x.val = x.val >= y.val
                x.tp = Bool
            else: x = CG.genRelation(op, x, y)
        else: mark('bad type')
    return x



#Procedure compoundStatement() parses
#	compoundStatement ::= "begin" statement {";" statement} "end"

def compoundStatement():
    if SC.sym == BEGIN: getSym()
    else: mark("'begin' expected")
    x = statement()
    while SC.sym == SEMICOLON or SC.sym in FIRSTSTATEMENT:
        if SC.sym == SEMICOLON: getSym()
        else: mark("; missing")
        y = statement(); x = CG.genSeq(x, y)
    if SC.sym == END: getSym()
    else: mark("'end' expected")
    return x


#Procedure controlVariable() parses
#	controlVariable ::= ident

def controlVariable():
    if SC.sym == IDENT:
        x = find(SC.val);
        x = CG.genVar(x)
    else:
        mark('Ident expected!!')
    return x


#Procedure constList() parses
#	constList ::= expression {“,” expression}

def constList():
    #empty list to add stuff
    xs = []
    #expression returns Var(Int)!! hopefully
    x = expression()
    #append it to the list
    xs.append(x)
    #while there are more elements in the list
    while SC.sym == COMMA:
        if SC.sym == COMMA: getSym()
        else: mark(", missing")
        #append it to the list
        y = expression()
        xs.append(y)
    #create Type(Array) with parameters (self, base, lower, length):
    #set lower to 0 since we are gonna access it starting from x[0]...
    x = Type(CG.genArray(Array(xs[0].tp, 0, len(xs))))
    #print(x)
    return x, xs


#Procedure initialValue() parses
#	initialValue ::= expression

def initialValue():
    x = expression()
    return x


#Procedure finalValue() parses
#	finalValue ::= expression

def finalValue():
    x = expression()
    return x


#Procedure case() parses
#	case :: = constList ":" statement

def case(x, counter_name, else_name):
    global array_num
    y, inputList = constList()
    #inorder to push it to the stack; get the ST.Array
    array_tp = y.val;
    #array_name starting from for_array_0
    array_name = "for_array_"+str(array_num)
    #declare it, and will create global variable in genForArray()
    newDecl(array_name, Var(array_tp))
    #increment array number
    array_num += 1
    #call genForArray with name of the array, user input array
    CG.genCaseArrayLoopInit(x, array_name, inputList, counter_name, else_name)
    if SC.sym == COLON:
        getSym()
        a = statement()
        CG.genCaseArrayLoopEnd(counter_name)
    else:
        mark("colon (:) expected from case function")



#Procedure elsePart() parses
#	elsePart ::= ("else"|"otherwise") statementlist

def elsePart(else_name):
    if (SC.sym == ELSE or SC.sym == OTHERWISE):
        getSym()
        CG.genCaseElseInit(else_name)
        x = statementList()
        CG.genCaseElseEnd()
    else:
        mark("else or otherwise expected from elsePart function")



#Procedure statementList() parses
#	statementlist ::= statement {";" statement}

def statementList():
    xs = []
    x = statement()
    xs.append(x)
    while SC.sym == SEMICOLON:
        if SC.sym == SEMICOLON:
            getSym()
        y = statement()
        if y == None:
            break
        xs.append(y)
    return xs



#Procedure statement() parses
#	statement ::=
#	    ident selector ":=" expression |
#    	ident "(" [expression {"," expression}] ")" |
#    	compoundStatement |
#    	"if" expression "then" statement ["else"statement] |
#    	"while" expression "do" statement |
#    	"case" expression "of" case {";" case} [elsePart] [";"] "end" |
#    	"for" controlVariable ":=" initialValue ("to"|"downto") finalValue "do" statement |
#    	"for" controlVariable "in" "[" constList "]" "do" statement

def statement():
    global array_num
    if SC.sym == END:
        return None
    if SC.sym not in FIRSTSTATEMENT:
        mark("statement expected"); getSym()
        while SC.sym not in FIRSTSTATEMENT | FOLLOWSTATEMENT | STRONGSYMS : getSym()
    if SC.sym == IDENT:
        x = find(SC.val); getSym()
        if type(x) in {Var, Ref}:
            x = CG.genVar(x); x = selector(x)
            if SC.sym == BECOMES:
                getSym(); y = expression()
                if x.tp == y.tp in {Bool, Int}: x = CG.genAssign(x, y)
                else: mark('incompatible assignment')
            elif SC.sym == EQ:
                mark(':= expected'); getSym(); y = expression()
            else: mark(':= expected')
        elif type(x) in {Proc, StdProc}:
            fp, ap, i = x.par, [], 0   #  list of formals, list of actuals
            if SC.sym == LPAREN:
                getSym()
                if SC.sym in FIRSTEXPRESSION:
                    y = expression()
                    if i < len(fp):
                        if (type(fp[i]) == Var or type(y) == Var) and \
                           fp[i].tp == y.tp:
                            if type(x) == Proc:
                                ap.append(CG.genActualPara(y, fp[i], i))
                        else: mark('illegal parameter mode')
                    else: mark('extra parameter')
                    i = i + 1
                    while SC.sym == COMMA:
                        getSym()
                        y = expression()
                        if i < len(fp):
                            if (type(fp[i]) == Var or type(y) == Var) and \
                               fp[i].tp == y.tp:
                                if type(x) == Proc:
                                    ap.append(CG.genActualPara(y, fp[i], i))
                            else: mark('illegal parameter mode')
                        else: mark('extra parameter')
                        i = i + 1
                if SC.sym == RPAREN: getSym()
                else: mark("')' expected")
            if i < len(fp): mark('too few parameters')
            elif type(x) == StdProc:
                if x.name == 'read': x = CG.genRead(y)
                elif x.name == 'write': x = CG.genWrite(y)
                elif x.name == 'writeln': x = CG.genWriteln()
            else: x = CG.genCall(x, ap)
        else: mark("variable or procedure expected")
    elif SC.sym == BEGIN: x = compoundStatement()
    elif SC.sym == IF:
        getSym(); x = expression();
        if x.tp == Bool: x = CG.genThen(x)
        else: mark('boolean expected')
        if SC.sym == THEN: getSym()
        else: mark("'then' expected")
        y = statement()
        if SC.sym == ELSE:
            if x.tp == Bool: y = CG.genElse(x, y)
            getSym(); z = statement()
            if x.tp == Bool: x = CG.genIfElse(x, y, z)
        else:
            if x.tp == Bool: x = CG.genIfThen(x, y)
    elif SC.sym == WHILE:
        getSym(); t = CG.genWhile(); x = expression()
        if x.tp == Bool: x = CG.genDo(x)
        else: mark('boolean expected')
        if SC.sym == DO: getSym()
        else: mark("'do' expected")
        y = statement()
        if x.tp == Bool: x = CG.genWhileDo(t, x, y)
    elif SC.sym == FOR:
        getSym();
        #x = ident
        x = controlVariable()
        getSym()
        ##for controlVariable "in"
        if SC.sym == IN:
            getSym()
            #if '['
            if SC.sym == LBRAK:
                getSym()
                #from constList, get Type(Array) and array of input
                y, inputList = constList()
                #inorder to push it to the stack; get the ST.Array
                array_tp = y.val;
                #array_name starting from for_array_0
                array_name = "for_array_"+str(array_num)
                #declare it, and will create global variable in genForArray()
                newDecl(array_name, Var(array_tp))
                #call genForArray with name of the array, user input array
                CG.genForArray(array_name, inputList)
                #open the scope to store local variable 
                openScope()
                #temp variable name starting from counter_0
                var_name = "counter_"+str(array_num)
                #Var int to initialize
                temp_var = Var(Int)
                #declare it, will create local variable in genForInit()
                newDecl(var_name, temp_var)
                #call genForInit with controlVariable(ident, array_name,
                #var_name, length of input Array)
                CG.genForInit(x, array_name, var_name, len(inputList))
                #increment array number so it doesn't declare same array name
                #if we have more than 1 array / variable
                array_num += 1
                #if ]
                if SC.sym == RBRAK:
                    getSym()
                    if SC.sym == DO: getSym()
                    else: mark("'do' expected from for loop")
                    #statement() prints all the stuff b/w begin and end
                    statement()
                    #genForEnd() to close the loop
                    CG.genForEnd()
                    #closeScope -> popping the local variable after the loop
                    closeScope()
                    
                else: mark("']' expected from for loop")
            else: mark("'[' expected from for loop")
        ###for controlVariable :=
        elif SC.sym == BECOMES:
            getSym()
            #init_value = initialValue; int value hopefully
            init_value = initialValue().val
            if (SC.sym == TO or SC.sym == DOWNTO):
                #set goes up to True if "to"; set to False if "downto"
                if (SC.sym == TO): goes_up = True;
                else: goes_up = False;
                getSym()
                #final_value = finalValue()
                final_value = finalValue().val
                #####setting up the array
                #input List having init_value to final_value
                inputList = []
                ####create list according goes_up
                if (init_value <= final_value and goes_up):
                    #create the list
                    while (init_value <= final_value):
                        inputList.append(Const(Int, init_value))
                        init_value = init_value + 1
                elif(init_value >= final_value and not goes_up):
                    #create the list
                    while (init_value >= final_value):
                        inputList.append(Const(Int, init_value))
                        init_value = init_value - 1
                #if user gives wrong combination of ("to/downto") and initialValue  and finalValue        
                else: mark("can't go upto "+str(final_value)+" from "+str(init_value)+" or vise versa")
                #make Type(Array) so we can pass it to the function
                y = Type(CG.genArray(Array(inputList[0].tp, 0, len(inputList)-1)))
                #inorder to push it to the stack; get the ST.Array
                array_tp = y.val;
                #array_name starting from for_array_0
                array_name = "for_array_"+str(array_num)
                #declare it, and will create global variable in genForArray()
                newDecl(array_name, Var(array_tp))
                #call genForArray with name of the array, user input array
                CG.genForArray(array_name, inputList)
                #open the scope to store local variable 
                openScope()
                #temp variable name starting from counter_0
                var_name = "counter_"+str(array_num)
                #Var int to initialize
                temp_var = Var(Int)
                #declare it, will create local variable in genForInit()
                newDecl(var_name, temp_var)
                #call genForInit with controlVariable(ident, array_name,
                #var_name, length of input Array)
                CG.genForInit(x, array_name, var_name, len(inputList))
                #increment array number so it doesn't declare same array name
                #if we have more than 1 array / variable
                array_num += 1
                if SC.sym == DO: getSym()
                else: mark("'do' expected from for loop")
                #statement() prints all the stuff b/w begin and end
                statement()
                #genForEnd() to close the loop
                CG.genForEnd()
                #closeScope -> popping the local variable after the loop
                closeScope()
                
            else:
                mark("to or downto expected from for loop")
        else: mark("in or := expected from for loop")
            
    ###case statement        
    elif SC.sym == CASE:
        getSym()
        #x = expression
        x = expression()
        #open the scope because all the stuff will be a local Var
        openScope()
        #Counter variable for indexing array returned by constList
        counter_name = "counter_"+str(array_num)
        #Var int to initialize
        temp_var = Var(Int)
        #declare counter variable
        newDecl(counter_name, temp_var)
        #else variable to track if any case matches expression.
        else_name = "else_"+str(array_num)
        #Var int to initialize
        temp_var = Var(Int)
        #declare else variable
        newDecl(else_name, temp_var)
        #increment array_num 
        array_num += 1
        #call CG.genCaseInit()
        CG.genCaseInit(counter_name, else_name)
        if SC.sym == OF:
            getSym()
            #call case where array for each case will be initialized
            #it needs counter name and else name in order to make a loop
            case(x, counter_name, else_name)
            while SC.sym == SEMICOLON:
                if (SC.sym == SEMICOLON):
                    getSym()
                case(x, counter_name, else_name)
            #elsePart needs variable else to check if else is set to
            #0 or 1. if set to 0, execute statementList else not
            elsePart(else_name)
            ###the last semicolon is taken care from elsePart -> statementlist
            if SC.sym == END:
                getSym() 
                #for setting current level back to original
                CG.genCaseEnd()
                #close the scope
                closeScope()
            else:
                mark("end expected from case statement")
        else:
            mark("of expected from case statement")
        
    else: x = None
    return x



#Procedure typ parses
#	type ::= ident |
#         "array" "[" expression ".." expression "]" "of" type |
#         "record" typedIds {";" typedIds} "end"

def typ():
    if SC.sym not in FIRSTTYPE:
        mark("type expected")
        while SC.sym not in FIRSTTYPE | FOLLOWTYPE | STRONGSYMS: getSym()
    if SC.sym == IDENT:
        ident = SC.val; x = find(ident); getSym()
        if type(x) == Type: x = Type(x.val);
        else: mark('not a type'); x = Type(None)
    elif SC.sym == ARRAY:
        getSym()
        if SC.sym == LBRAK: getSym()
        else: mark("'[' expected")
        x = expression()
        if SC.sym == PERIOD: getSym()
        else: mark("'.' expected")
        if SC.sym == PERIOD: getSym()
        else: mark("'.' expected")
        y = expression()
        if SC.sym == RBRAK: getSym()
        else: mark("']' expected")
        if SC.sym == OF: getSym()
        else: mark("'of' expected")
        #type of data
        z = typ().val;
        if type(x) != Const or x.val < 0:
            mark('bad lower bound'); x = Type(None)
        elif type(y) != Const or y.val < x.val:
            mark('bad upper bound'); x = Type(None)
        #Array base type, lower value, length
        else: x = Type(CG.genArray(Array(z, x.val, y.val - x.val + 1)))
    elif SC.sym == RECORD:
        getSym(); openScope(); typedIds(Var)
        while SC.sym == SEMICOLON:
            getSym(); typedIds(Var)
        if SC.sym == END: getSym()
        else: mark("'end' expected")
        r = topScope(); closeScope()
        x = Type(CG.genRec(Record(r)))
    else: x = Type(None)
    return x


#Procedure typeIds(kind) parses
#	typedIds ::= ident {"," ident} ":" type.

def typedIds(kind):
    if SC.sym == IDENT: tid = [SC.val]; getSym()
    else: mark("identifier expected"); tid = []
    while SC.sym == COMMA:
        getSym()
        if SC.sym == IDENT: tid.append(SC.val); getSym()
        else: mark('identifier expected')
    if SC.sym == COLON:
        getSym(); tp = typ().val
        #print('value of tp : '+str(kind(tp)))
        if tp != None:
            #print('kind(tp) :'+str(kind(tp)))
            for i in tid: newDecl(i, kind(tp))
    else: mark("':' expected")


#Procedure declarations(allocVar) parses
#declarations ::=
#    {"const" ident "=" expression ";"}
#    {"type" ident "=" type ";"}
#    {"var" typedIds ";"}
#    {"procedure" ident ["(" [["var"] typedIds {";" ["var"] typedIds}] ")"] ";"
#        declarations compoundStatement ";"}    

def declarations(allocVar):
    if SC.sym not in FIRSTDECL | FOLLOWDECL:
        mark("'begin' or declaration expected")
        while SC.sym not in FIRSTDECL | FOLLOWDECL | STRONGSYMS: getSym()
    while SC.sym == CONST:
        getSym()
        if SC.sym == IDENT:
            ident = SC.val; getSym()
            if SC.sym == EQ: getSym()
            else: mark("= expected")
            x = expression()
            if type(x) == Const: newDecl(ident, x)
            else: mark('expression not constant')
        else: mark("constant name expected")
        if SC.sym == SEMICOLON: getSym()
        else: mark("; expected")
    while SC.sym == TYPE:
        getSym()
        if SC.sym == IDENT:
            ident = SC.val; getSym()
            if SC.sym == EQ: getSym()
            else: mark("= expected")
            x = typ(); newDecl(ident, x)  #  x is of type ST.Type
            if SC.sym == SEMICOLON: getSym()
            else: mark("; expected")
        else: mark("type name expected")
    start = len(topScope())
    while SC.sym == VAR:
        getSym(); typedIds(Var)
        if SC.sym == SEMICOLON: getSym()
        else: mark("; expected")
    varsize = allocVar(topScope(), start)
    while SC.sym == PROCEDURE:
        getSym()
        if SC.sym == IDENT: getSym()
        else: mark("procedure name expected")
        ident = SC.val; newDecl(ident, Proc([])) #  entered without parameters
        sc = topScope()
        openScope() # new scope for parameters and body
        if SC.sym == LPAREN:
            getSym()
            if SC.sym in {VAR, IDENT}:
                if SC.sym == VAR: getSym(); typedIds(Ref)
                else: typedIds(Var)
                while SC.sym == SEMICOLON:
                    getSym()
                    if SC.sym == VAR: getSym(); typedIds(Ref)
                    else: typedIds(Var)
            else: mark("formal parameters expected")
            fp = topScope()
            sc[-1].par = fp[:] #  procedure parameters updated
            if SC.sym == RPAREN: getSym()
            else: mark(") expected")
        else: fp = []
        parsize = CG.genProcStart(ident, fp)
        if SC.sym == SEMICOLON: getSym()
        else: mark("; expected")
        localsize = declarations(CG.genLocalVars)
        CG.genProcEntry(ident, parsize, localsize)
        x = compoundStatement(); CG.genProcExit(x, parsize, localsize)
        closeScope() #  scope for parameters and body closed
        if SC.sym == SEMICOLON: getSym()
        else: mark("; expected")
    return varsize


#Procedure program parses
#    program ::= "program" ident ";" declarations compoundStatement    

def program():
    newDecl('boolean', Type(CG.genBool(Bool)))
    newDecl('integer', Type(CG.genInt(Int)))
    newDecl('true', Const(Bool, 1))
    newDecl('false', Const(Bool, 0))
    newDecl('read', StdProc([Ref(Int)]))
    newDecl('write', StdProc([Var(Int)]))
    newDecl('writeln', StdProc([]))
    CG.genProgStart()
    if SC.sym == PROGRAM: getSym()
    else: mark("'program' expected")
    ident = SC.val
    if SC.sym == IDENT: getSym()
    else: mark('program name expected')
    if SC.sym == SEMICOLON: getSym()
    else: mark('; expected')
    declarations(CG.genGlobalVars); CG.genProgEntry(ident)
    x = compoundStatement()
    return CG.genProgExit(x)


#Procedure compileString(src, dstfn, target) compiles the source as given by string src; 
#if dstfn is provided, the code is written to a file by that name, 
#otherwise printed on the screen. If target is omitted, MIPS code is generated.    

def compileString(src, dstfn = None, target = 'wat'):
    global CG
    #array_num###
    global array_num
    array_num = 0
    if target == 'wat': import CGwat as CG
    elif target == 'mips': import CGmips as CG
    elif target == 'ast': import CGast as CG
    else: print('unknown target'); return
    SC.init(src)
    ST.init()
    p = program()
    if p != None and not SC.error:
        if dstfn == None: print(p)
        else:
            with open(dstfn, 'w') as f: f.write(p);



#Procedure compileFile(srcfn, target) compiles the file named scrfn, 
#which must have the extension .p, and generates assembly code in a file 
#with extension .s. If target is omitted, MIPS code is generated.            

def compileFile(srcfn, target = 'wat'):
    if srcfn.endswith('.p'):
        with open(srcfn, 'r') as f: src = f.read()
        dstfn = srcfn[:-2] + '.s'
        compileString(src, dstfn, target)
    else: print("'.p' file extension expected")











