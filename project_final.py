import nbimporter; nbimporter.options["only_defs"] = False
import P0, SC

P0.compileString("""
program p;
  var x, y: integer;
  begin
    x := 3;
    case x of 3,5 : begin write(x) end; 2,4 : begin write(x) end else begin write(x+2); end ; end 
  end
""", target = 'wat')


P0.compileString("""
program p;
  var x, y: integer;
  begin
    for y in [1, 3, 5] do                  {writes 9, 8, 7, 6, 5, 4}
        for x in [2, 4, 6] do
            begin write(x + y) end;
      begin writeln() end;
    writeln()             {writes 3}
  end
""", target = 'wat')