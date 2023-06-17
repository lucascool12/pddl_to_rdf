function translate_pddl() {
  const xhttp = new XMLHttpRequest();
  xhttp.open("POST", "/translate_pddl", true);
  xhttp.onload = function() {
    let rdf = document.getElementById("rdf");
    rdf.value = this.responseText;
  }
  const pddl = document.getElementById("pddl").value;
  xhttp.send(pddl);
}

function Bool(initialValue) {
    var bool = !!initialValue;
    var listeners = [];
    var returnVal = function(value) {
        if (arguments.length) {
            var oldValue = bool;
            bool = !!value;
            listeners.forEach(function (listener, i, list) {
                listener.call(returnVal, { oldValue: oldValue, newValue: bool });
            });
        }
        return bool
    };
    returnVal.addListener = function(fn) {
        if (typeof fn == "function") {
            listeners.push(fn);
        }
        else {
            throw "Not a function!";
        }
    };
    return returnVal;
}

// from https://stackdiary.com/tutorials/create-table-javascript/
function createTableFromObjects(data) {
  const table = document.createElement('table');
  const headerRow = document.createElement('tr');
  
  // Create table header row
  if (data.length <= 0) {
    const headerCell = document.createElement('th');
    headerCell.textContent = "No results";
    headerRow.appendChild(headerCell);
    table.appendChild(headerRow);
    return table
  }
  const keys = data[0].keys();
  for (const key of keys) {
    const headerCell = document.createElement('th');
    headerCell.textContent = key.value;
    headerRow.appendChild(headerCell);
  }
  table.appendChild(headerRow);

  // Create table data rows
  for (const obj of data) {
    const dataRow = document.createElement('tr');
    console.debug(obj);
    const keys = data[0].keys();
    for (const key of keys) {
      const dataCell = document.createElement('td');
      if (obj.has(key)) {
        dataCell.textContent = obj.get(key).value;
      } else {
        dataCell.textContent = "";
      }
      console.debug(obj.get(key));
      dataRow.appendChild(dataCell);
    }
    table.appendChild(dataRow);
  }

  return table;
}

function query() {
  console.log("here")
  const qel = document.getElementById("sparql");
  const query = qel.value;
  const rdfel = document.getElementById("rdf");
  const rdf = rdfel.value;
  console.log(query);
  const parser = new N3.Parser();
  let store = new N3.Store();
  const { namedNode, literal, defaultGraph, quad } = N3.DataFactory
  let ready = Bool(false);
  try {
  parser.parse(rdf,
    function(error, triple) {
      if (error) {
        window.alert("Parser error : " + error);
        return;
      }
      if (triple) {
        store.addQuad(
          quad(
            triple.subject,
            triple.predicate,
            triple.object
          )
        );
      } else {
        console.log("Parsed.")
        ready(true);
      }
    }
  );
  } catch (error) {
    window.alert("Parser error : " + error);
    return;
  }
  ready.addListener((e) => {
    let d = new Comunica.QueryEngine().queryBindings(
      query,
      {
        sources: [ store ],
      }
    );
    d.then(function(bindingsStream) {
      let binding_data = [];
      // bindingsStream.catch((error) => {window.alert(error)} );
      bindingsStream.on('data', (binding) => {
        console.log(binding.toString());
        binding_data.push(binding);
      })
      bindingsStream.on('end', () => {
        let output_el = document.getElementById("sparql_output");
        if (output_el.firstElementChild !== null) {
          output_el.removeChild(output_el.firstElementChild);
        }
        let table = createTableFromObjects(binding_data);
        output_el.appendChild(table);
      });
      bindingsStream.on('error', (error) => {
        window.alert(error);
        return;
      });
    });
    d.catch((error) => {window.alert(error); return;} )
  });
}

document.addEventListener("readystatechange", function(event) {
  let pddl = document.getElementById("pddl");
  if(pddl.textContent === null) { return }
  pddl.value =
  `; from https://github.com/yarox/pddl-examples
(define (domain rover-domain)
    (:requirements :fluents)
    
    (:functions
        (battery-amount ?rover)
        (sample-amount ?rover)
        (battery-capacity)
        (sample-capacity)
    )
    
    (:predicates
        (can-move ?from-waypoint ?to-waypoint)
        (is-visible ?objective ?waypoint)                       
        (is-in ?sample ?waypoint)
        (been-at ?rover ?waypoint)
        (carry ?rover ?sample)  
        (at ?rover ?waypoint)
        (is-recharging-dock ?waypoint)
        (is-dropping-dock ?waypoint)
        (taken-image ?objective)
        (stored-sample ?sample)
        (objective ?objective)
        (waypoint ?waypoint)    
        (sample ?sample) 
        (rover ?rover)                             
    )
    
    (:action move
        :parameters 
            (?rover
             ?from-waypoint 
             ?to-waypoint)

        :precondition 
            (and 
                (rover ?rover)
                (waypoint ?from-waypoint)
                (waypoint ?to-waypoint) 
                (at ?rover ?from-waypoint)
                (can-move ?from-waypoint ?to-waypoint)
                (> (battery-amount ?rover) 8))

        :effect 
            (and 
                (at ?rover ?to-waypoint)
                (been-at ?rover ?to-waypoint)
                (not (at ?rover ?from-waypoint))
                (decrease (battery-amount ?rover) 8))
    )

    (:action take-sample
        :parameters 
            (?rover 
             ?sample 
             ?waypoint)

        :precondition 
            (and 
                (rover ?rover)
                (sample ?sample)
                (waypoint ?waypoint) 
                (is-in ?sample ?waypoint)
                (at ?rover ?waypoint)
                (> (battery-amount ?rover) 3)
                (< (sample-amount ?rover) (sample-capacity)))

        :effect 
            (and 
                (not (is-in ?sample ?waypoint))
                (carry ?rover ?sample)
                (decrease (battery-amount ?rover) 3)
                (increase (sample-amount ?rover) 1))
    )
    
    (:action drop-sample
        :parameters 
            (?rover
             ?sample 
             ?waypoint)

        :precondition 
            (and 
                (rover ?rover)
                (sample ?sample)
                (waypoint ?waypoint)
                (is-dropping-dock ?waypoint)
                (at ?rover ?waypoint)
                (carry ?rover ?sample)
                (> (battery-amount ?rover) 2))                     
                           
        :effect 
            (and 
                (is-in ?sample ?waypoint) 
                (not (carry ?rover ?sample))
                (stored-sample ?sample)
                (decrease (battery-amount ?rover) 2)
                (decrease (sample-amount ?rover) 1))
    )

    (:action take-image
        :parameters 
            (?rover
             ?objective 
             ?waypoint)

        :precondition 
            (and 
                (rover ?rover)
                (objective ?objective)
                (waypoint ?waypoint)
                (at ?rover ?waypoint)
                (is-visible ?objective ?waypoint)
                (> (battery-amount ?rover) 1))
                           
        :effect 
            (and 
                (taken-image ?objective)
                (decrease (battery-amount ?rover) 1))
    )
    
    (:action recharge
        :parameters 
            (?rover
             ?waypoint)
        
        :precondition
	        (and
	            (rover ?rover)
	            (waypoint ?waypoint)  
	            (at ?rover ?waypoint)
	            (is-recharging-dock ?waypoint) 
	            (< (battery-amount ?rover) 20))
	            
        :effect
            (increase (battery-amount ?rover) 
                (- (battery-capacity) (battery-amount ?rover)))
    )
)`;
  let sparql = document.getElementById("sparql");
  sparql.value = `PREFIX ont: <http://example.com/pddl_ont/>
PREFIX ex: <http://example.com/test/>
SELECT ?p ?name
WHERE
{
  ?p a ont:Function.
  OPTIONAL { ?p ont:hasParameters/ont:parameterName ?name. }
}`
})
