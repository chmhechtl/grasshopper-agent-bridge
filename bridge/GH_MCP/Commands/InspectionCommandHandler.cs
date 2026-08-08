using System;
using System.Collections.Generic;
using GrasshopperMCP.Models;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Parameters;
using Rhino;
using System.Linq;
using System.Threading;

namespace GrasshopperMCP.Commands
{
    /// <summary>
    /// Read-only inspection commands plus targeted delete, added for the China course sessions.
    /// </summary>
    public static class InspectionCommandHandler
    {
        private static object RunOnUiThread(Func<GH_Document, object> action)
        {
            object result = null;
            Exception exception = null;

            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                try
                {
                    var doc = Grasshopper.Instances.ActiveCanvas?.Document;
                    if (doc == null)
                    {
                        throw new InvalidOperationException("No active Grasshopper document");
                    }
                    result = action(doc);
                }
                catch (Exception ex)
                {
                    exception = ex;
                }
            }));

            while (result == null && exception == null)
            {
                Thread.Sleep(10);
            }

            if (exception != null)
            {
                throw exception;
            }
            return result;
        }

        /// <summary>
        /// Returns every component/param that currently reports runtime errors, warnings or remarks.
        /// </summary>
        public static object GetErrors(Command command)
        {
            return RunOnUiThread(doc =>
            {
                var levels = new[]
                {
                    GH_RuntimeMessageLevel.Error,
                    GH_RuntimeMessageLevel.Warning,
                    GH_RuntimeMessageLevel.Remark
                };

                var components = new List<object>();
                foreach (var obj in doc.Objects)
                {
                    var active = obj as IGH_ActiveObject;
                    if (active == null)
                    {
                        continue;
                    }

                    var messages = new List<object>();
                    foreach (var level in levels)
                    {
                        foreach (var message in active.RuntimeMessages(level))
                        {
                            messages.Add(new { level = level.ToString(), message });
                        }
                    }

                    if (messages.Count > 0)
                    {
                        components.Add(new
                        {
                            id = obj.InstanceGuid.ToString(),
                            type = obj.GetType().Name,
                            name = obj.Name,
                            nickname = obj.NickName,
                            x = obj.Attributes != null ? obj.Attributes.Pivot.X : 0f,
                            y = obj.Attributes != null ? obj.Attributes.Pivot.Y : 0f,
                            messages
                        });
                    }
                }

                return new { count = components.Count, components };
            });
        }

        /// <summary>
        /// Returns every wire in the document, resolved to top-level component ids.
        /// </summary>
        public static object GetConnections(Command command)
        {
            return RunOnUiThread(doc =>
            {
                var connections = new List<object>();

                void AddSourcesOf(IGH_Param input, IGH_DocumentObject targetOwner)
                {
                    foreach (var source in input.Sources)
                    {
                        var sourceOwner = source.Attributes?.GetTopLevel?.DocObject;
                        connections.Add(new
                        {
                            sourceId = (sourceOwner ?? (IGH_DocumentObject)source).InstanceGuid.ToString(),
                            sourceName = (sourceOwner ?? (IGH_DocumentObject)source).NickName,
                            sourceParam = source.Name,
                            targetId = targetOwner.InstanceGuid.ToString(),
                            targetName = targetOwner.NickName,
                            targetParam = input.Name
                        });
                    }
                }

                foreach (var obj in doc.Objects)
                {
                    if (obj is IGH_Component component)
                    {
                        foreach (var input in component.Params.Input)
                        {
                            AddSourcesOf(input, component);
                        }
                    }
                    else if (obj is IGH_Param param)
                    {
                        AddSourcesOf(param, param);
                    }
                }

                return new { count = connections.Count, connections };
            });
        }

        /// <summary>
        /// Creates a labeled canvas group around the given component ids.
        /// </summary>
        public static object CreateGroup(Command command)
        {
            string name = command.GetParameter<string>("name");
            var idArray = command.GetParameter<Newtonsoft.Json.Linq.JArray>("ids");
            string colorHex = command.GetParameter<string>("color");

            if (idArray == null || idArray.Count == 0)
            {
                throw new ArgumentException("Parameter 'ids' (list of component ids) is required");
            }

            return RunOnUiThread(doc =>
            {
                var group = new Grasshopper.Kernel.Special.GH_Group();
                group.CreateAttributes();
                group.NickName = name ?? string.Empty;
                if (!string.IsNullOrEmpty(colorHex))
                {
                    group.Colour = System.Drawing.ColorTranslator.FromHtml(colorHex);
                }

                int added = 0;
                foreach (var token in idArray)
                {
                    if (Guid.TryParse(token.ToString(), out var memberId) && doc.FindObject(memberId, true) != null)
                    {
                        group.AddObject(memberId);
                        added++;
                    }
                }
                if (added == 0)
                {
                    throw new ArgumentException("None of the given ids exist in the document");
                }

                doc.AddObject(group, false);
                group.ExpireCaches();
                return new { id = group.InstanceGuid.ToString(), name = group.NickName, members = added };
            });
        }

        /// <summary>
        /// Removes wires feeding one input of a component. With sourceId only that wire is removed.
        /// </summary>
        public static object DisconnectComponents(Command command)
        {
            string targetIdStr = command.GetParameter<string>("targetId");
            string targetParamName = command.GetParameter<string>("targetParam");
            string sourceIdStr = command.GetParameter<string>("sourceId");

            if (string.IsNullOrEmpty(targetIdStr) || !Guid.TryParse(targetIdStr, out var targetId))
            {
                throw new ArgumentException("Valid targetId is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(targetId, true);
                if (obj == null)
                {
                    throw new ArgumentException($"Component with ID {targetIdStr} not found");
                }

                IGH_Param input = null;
                if (obj is IGH_Component component)
                {
                    if (string.IsNullOrEmpty(targetParamName))
                    {
                        throw new ArgumentException("targetParam is required for components");
                    }
                    input = component.Params.Input.FirstOrDefault(p =>
                        p.Name.Equals(targetParamName, StringComparison.OrdinalIgnoreCase) ||
                        p.NickName.Equals(targetParamName, StringComparison.OrdinalIgnoreCase));
                    if (input == null)
                    {
                        throw new ArgumentException($"Input '{targetParamName}' not found");
                    }
                }
                else if (obj is IGH_Param param)
                {
                    input = param;
                }
                else
                {
                    throw new ArgumentException("Target is neither component nor parameter");
                }

                int before = input.SourceCount;
                if (!string.IsNullOrEmpty(sourceIdStr) && Guid.TryParse(sourceIdStr, out var sourceId))
                {
                    foreach (var source in input.Sources.ToList())
                    {
                        var owner = source.Attributes?.GetTopLevel?.DocObject;
                        if (source.InstanceGuid == sourceId || (owner != null && owner.InstanceGuid == sourceId))
                        {
                            input.RemoveSource(source);
                        }
                    }
                }
                else
                {
                    input.RemoveAllSources();
                }

                input.ExpireSolution(false);
                doc.NewSolution(false);
                return new { removedWires = before - input.SourceCount, remaining = input.SourceCount };
            });
        }

        /// <summary>
        /// Selects an entry of a GH_ValueList by item name or index.
        /// </summary>
        public static object SetValueList(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            string value = command.GetParameter<string>("value");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }
            if (string.IsNullOrEmpty(value))
            {
                throw new ArgumentException("Parameter 'value' (item name or index) is required");
            }

            return RunOnUiThread(doc =>
            {
                var vl = doc.FindObject(id, true) as Grasshopper.Kernel.Special.GH_ValueList;
                if (vl == null)
                {
                    throw new ArgumentException($"No value list with ID {idStr}");
                }

                int index = -1;
                for (int i = 0; i < vl.ListItems.Count; i++)
                {
                    if (vl.ListItems[i].Name.Equals(value, StringComparison.OrdinalIgnoreCase))
                    {
                        index = i;
                        break;
                    }
                }
                if (index < 0 && !int.TryParse(value, out index))
                {
                    var names = string.Join(", ", vl.ListItems.Select(li => li.Name));
                    throw new ArgumentException($"Item '{value}' not found. Items: {names}");
                }
                if (index < 0 || index >= vl.ListItems.Count)
                {
                    throw new ArgumentException($"Index {index} out of range (0..{vl.ListItems.Count - 1})");
                }

                vl.SelectItem(index);
                vl.ExpireSolution(false);
                doc.NewSolution(false);
                return new { id = idStr, selected = vl.ListItems[index].Name, index };
            });
        }

        /// <summary>
        /// Dumps the volatile output data of a component or parameter as strings.
        /// </summary>
        public static object GetComponentOutput(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            int limit;
            try { limit = command.GetParameter<int>("limit"); } catch { limit = 0; }
            if (limit <= 0) { limit = 50; }

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                if (obj == null)
                {
                    throw new ArgumentException($"Component with ID {idStr} not found");
                }

                object Dump(IGH_Param p)
                {
                    var items = new List<string>();
                    foreach (var goo in p.VolatileData.AllData(true))
                    {
                        if (items.Count >= limit) { break; }
                        items.Add(goo?.ToString() ?? "<null>");
                    }
                    return new { name = p.Name, count = p.VolatileDataCount, items };
                }

                var outputs = new List<object>();
                if (obj is IGH_Component component)
                {
                    outputs.AddRange(component.Params.Output.Select(p => (object)Dump(p)));
                }
                else if (obj is IGH_Param param)
                {
                    outputs.Add(Dump(param));
                }
                else
                {
                    throw new ArgumentException("Object has no data outputs");
                }

                return new { id = idStr, outputs };
            });
        }

        /// <summary>
        /// Wire attachment points of one object's parameters, in canvas coordinates.
        /// A standalone parameter (slider, panel, value list) reports its own grip.
        /// </summary>
        private static List<object> Grips(IGH_DocumentObject obj, bool wantInput)
        {
            var grips = new List<object>();

            void Add(string name, IGH_Attributes attributes)
            {
                if (attributes == null) { return; }
                var point = wantInput ? attributes.InputGrip : attributes.OutputGrip;
                grips.Add(new { name, x = point.X, y = point.Y });
            }

            if (obj is IGH_Component component)
            {
                foreach (var param in wantInput ? component.Params.Input : component.Params.Output)
                {
                    Add(param.Name, param.Attributes);
                }
            }
            else if (obj is IGH_Param standalone)
            {
                Add(standalone.Name, standalone.Attributes);
            }

            return grips;
        }

        /// <summary>
        /// Returns position, size and group membership of every object — the input an
        /// auto-layout pass needs.
        /// </summary>
        public static object GetLayout(Command command)
        {
            return RunOnUiThread(doc =>
            {
                var groups = new List<object>();
                var objects = new List<object>();

                foreach (var obj in doc.Objects)
                {
                    if (obj is Grasshopper.Kernel.Special.GH_Group group)
                    {
                        groups.Add(new
                        {
                            id = group.InstanceGuid.ToString(),
                            name = group.NickName,
                            members = group.ObjectIDs.Select(g => g.ToString()).ToList()
                        });
                        continue;
                    }

                    var bounds = obj.Attributes != null
                        ? obj.Attributes.Bounds
                        : new System.Drawing.RectangleF();
                    objects.Add(new
                    {
                        id = obj.InstanceGuid.ToString(),
                        type = obj.GetType().Name,
                        name = obj.Name,
                        nickname = obj.NickName,
                        x = obj.Attributes != null ? obj.Attributes.Pivot.X : 0f,
                        y = obj.Attributes != null ? obj.Attributes.Pivot.Y : 0f,
                        // Bounds origin, because Pivot sits somewhere inside the box and
                        // differs per attribute type — overlap maths needs the real rectangle.
                        left = bounds.X,
                        top = bounds.Y,
                        width = bounds.Width,
                        height = bounds.Height,
                        // Wire attachment points, so a layout pass can make a
                        // connection perfectly horizontal instead of guessing.
                        inputs = Grips(obj, wantInput: true),
                        outputs = Grips(obj, wantInput: false)
                    });
                }

                return new { objectCount = objects.Count, objects, groups };
            });
        }

        /// <summary>
        /// Moves a component to an absolute canvas position. Accepts a single {id,x,y} or a
        /// batch via "items": [{id,x,y}, ...] so a whole layout lands in one solution.
        /// </summary>
        public static object SetComponentPosition(Command command)
        {
            var items = new List<Tuple<Guid, float, float>>();
            var batch = command.GetParameter<Newtonsoft.Json.Linq.JArray>("items");

            if (batch != null)
            {
                foreach (var token in batch)
                {
                    if (Guid.TryParse((string)token["id"], out var itemId))
                    {
                        items.Add(Tuple.Create(itemId, (float)token["x"], (float)token["y"]));
                    }
                }
            }
            else
            {
                string idStr = command.GetParameter<string>("id");
                if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var singleId))
                {
                    throw new ArgumentException("Valid component id (or 'items' array) is required");
                }
                items.Add(Tuple.Create(singleId,
                    (float)command.GetParameter<double>("x"),
                    (float)command.GetParameter<double>("y")));
            }

            if (items.Count == 0)
            {
                throw new ArgumentException("No valid items to position");
            }

            return RunOnUiThread(doc =>
            {
                int moved = 0;
                var missing = new List<string>();
                foreach (var item in items)
                {
                    var obj = doc.FindObject(item.Item1, true);
                    if (obj == null || obj.Attributes == null)
                    {
                        missing.Add(item.Item1.ToString());
                        continue;
                    }
                    obj.Attributes.Pivot = new System.Drawing.PointF(item.Item2, item.Item3);
                    obj.Attributes.ExpireLayout();
                    moved++;
                }
                doc.DestroyAttributeCache();
                Grasshopper.Instances.ActiveCanvas?.Refresh();
                return new { moved, missing };
            });
        }

        /// <summary>
        /// Resizes a component's box on the canvas — mainly for panels, whose default box is
        /// too small for generated RAPID code.
        /// </summary>
        public static object SetComponentSize(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            double width = command.GetParameter<double>("width");
            double height = command.GetParameter<double>("height");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }
            if (width <= 0 || height <= 0)
            {
                throw new ArgumentException("width and height must be positive");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                if (obj == null || obj.Attributes == null)
                {
                    throw new ArgumentException($"Component with ID {idStr} not found");
                }

                var bounds = obj.Attributes.Bounds;
                obj.Attributes.Bounds = new System.Drawing.RectangleF(
                    bounds.X, bounds.Y, (float)width, (float)height);
                obj.Attributes.ExpireLayout();
                doc.DestroyAttributeCache();
                Grasshopper.Instances.ActiveCanvas?.Refresh();

                return new { id = idStr, width, height };
            });
        }

        /// <summary>
        /// Renames a component — the label the user reads on the canvas.
        /// A panel showing "4" tells nobody it means cardboard thickness.
        /// </summary>
        public static object SetNickname(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            string name = command.GetParameter<string>("name");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }
            if (name == null)
            {
                throw new ArgumentException("Parameter 'name' is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                if (obj == null)
                {
                    throw new ArgumentException($"Component with ID {idStr} not found");
                }

                obj.NickName = name;
                obj.Attributes?.ExpireLayout();
                doc.DestroyAttributeCache();
                Grasshopper.Instances.ActiveCanvas?.Refresh();

                return new { id = idStr, nickname = obj.NickName };
            });
        }

        /// <summary>
        /// Configures a number slider completely: range, value, decimals, integer mode.
        /// </summary>
        public static object SetSlider(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }

            double min = command.GetParameter<double>("min");
            double max = command.GetParameter<double>("max");
            double value = command.GetParameter<double>("value");
            int digits;
            try { digits = command.GetParameter<int>("digits"); } catch { digits = -1; }
            string name = command.GetParameter<string>("name");

            if (max <= min)
            {
                throw new ArgumentException("max must be greater than min");
            }

            return RunOnUiThread(doc =>
            {
                var slider = doc.FindObject(id, true) as Grasshopper.Kernel.Special.GH_NumberSlider;
                if (slider == null)
                {
                    throw new ArgumentException($"No number slider with ID {idStr}");
                }

                // Integer sliders when no decimals are asked for — clean increments
                // beat a value list of 0.01 steps nobody wants to hit.
                slider.Slider.Type = digits <= 0
                    ? Grasshopper.GUI.Base.GH_SliderAccuracy.Integer
                    : Grasshopper.GUI.Base.GH_SliderAccuracy.Float;
                if (digits > 0)
                {
                    slider.Slider.DecimalPlaces = digits;
                }

                slider.Slider.Minimum = (decimal)min;
                slider.Slider.Maximum = (decimal)max;
                slider.SetSliderValue((decimal)Math.Max(min, Math.Min(max, value)));

                if (!string.IsNullOrEmpty(name))
                {
                    slider.NickName = name;
                }

                slider.ExpireSolution(false);
                slider.Attributes?.ExpireLayout();
                doc.NewSolution(false);

                return new
                {
                    id = idStr,
                    nickname = slider.NickName,
                    min,
                    max,
                    value = (double)slider.CurrentValue
                };
            });
        }

        /// <summary>
        /// Writes a value straight into a component's input, no panel needed.
        /// Constants like "1" deserve no canvas real estate.
        /// </summary>
        public static object SetParamValue(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            int index = command.GetParameter<int>("index");
            string value = command.GetParameter<string>("value");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }
            if (value == null)
            {
                throw new ArgumentException("Parameter 'value' is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                IGH_Param param = obj is IGH_Component component
                    ? (index >= 0 && index < component.Params.Input.Count ? component.Params.Input[index] : null)
                    : obj as IGH_Param;
                if (param == null)
                {
                    throw new ArgumentException($"No input {index} on {idStr}");
                }
                if (param.SourceCount > 0)
                {
                    throw new InvalidOperationException(
                        "Input is wired — a persistent value would be ignored. Disconnect first.");
                }

                string kind;
                switch (param)
                {
                    case Param_Integer integerParam:
                        integerParam.PersistentData.Clear();
                        integerParam.PersistentData.Append(
                            new Grasshopper.Kernel.Types.GH_Integer(int.Parse(value)));
                        kind = "integer";
                        break;
                    case Param_Number numberParam:
                        numberParam.PersistentData.Clear();
                        numberParam.PersistentData.Append(
                            new Grasshopper.Kernel.Types.GH_Number(double.Parse(value,
                                System.Globalization.CultureInfo.InvariantCulture)));
                        kind = "number";
                        break;
                    case Param_Boolean booleanParam:
                        booleanParam.PersistentData.Clear();
                        booleanParam.PersistentData.Append(
                            new Grasshopper.Kernel.Types.GH_Boolean(bool.Parse(value)));
                        kind = "boolean";
                        break;
                    case Param_String stringParam:
                        stringParam.PersistentData.Clear();
                        stringParam.PersistentData.Append(
                            new Grasshopper.Kernel.Types.GH_String(value));
                        kind = "text";
                        break;
                    default:
                        throw new ArgumentException(
                            $"Cannot set a persistent value on {param.GetType().Name}");
                }

                param.ExpireSolution(false);
                doc.NewSolution(false);
                return new { id = idStr, index, value, kind };
            });
        }

        /// <summary>
        /// Shows or hides a component's viewport preview — intermediate geometry
        /// (bounding boxes, raw contours) clutters the model view.
        /// </summary>
        public static object SetPreview(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            bool hidden = command.GetParameter<bool>("hidden");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true) as IGH_PreviewObject;
                if (obj == null)
                {
                    throw new ArgumentException($"{idStr} has no viewport preview");
                }
                obj.Hidden = hidden;
                doc.NewSolution(false);
                Grasshopper.Instances.ActiveCanvas?.Refresh();
                return new { id = idStr, hidden };
            });
        }

        /// <summary>
        /// Sets a colour swatch, so previews get sensible defaults without hand-picking.
        /// </summary>
        public static object SetColour(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            string hex = command.GetParameter<string>("colour");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }
            if (string.IsNullOrEmpty(hex))
            {
                throw new ArgumentException("Parameter 'colour' (e.g. #A0785A) is required");
            }

            return RunOnUiThread(doc =>
            {
                var swatch = doc.FindObject(id, true) as Grasshopper.Kernel.Special.GH_ColourSwatch;
                if (swatch == null)
                {
                    throw new ArgumentException($"No colour swatch with ID {idStr}");
                }
                swatch.SwatchColour = System.Drawing.ColorTranslator.FromHtml(hex);
                swatch.ExpireSolution(true);
                return new { id = idStr, colour = hex };
            });
        }

        /// <summary>
        /// Fills a script component with source code. Mac Rhino 7 ships no vanilla
        /// component that writes a file, so an export button needs a scripted one.
        /// </summary>
        public static object SetScript(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            string code = command.GetParameter<string>("code");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }
            if (code == null)
            {
                throw new ArgumentException("Parameter 'code' is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                if (obj == null)
                {
                    throw new ArgumentException($"Component with ID {idStr} not found");
                }

                var property = obj.GetType().GetProperty("Code")
                               ?? obj.GetType().GetProperty("ScriptSource");
                if (property == null || !property.CanWrite)
                {
                    throw new ArgumentException($"{obj.GetType().Name} takes no source code");
                }

                property.SetValue(obj, code);
                (obj as IGH_ActiveObject)?.ExpireSolution(false);
                doc.NewSolution(false);

                return new { id = idStr, lines = code.Split('\n').Length };
            });
        }

        /// <summary>
        /// Searches Grasshopper's own component registry by name. Ends the GUID guesswork:
        /// returns guid, exact name, category and whether the proxy is obsolete.
        /// </summary>
        public static object SearchComponents(Command command)
        {
            string query = command.GetParameter<string>("query");
            if (string.IsNullOrWhiteSpace(query))
            {
                throw new ArgumentException("Parameter 'query' is required");
            }

            object result = null;
            Exception exception = null;

            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                try
                {
                    var matches = Grasshopper.Instances.ComponentServer.ObjectProxies
                        .Where(p => p.Desc.Name.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0 ||
                                    p.Desc.NickName.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0)
                        .OrderBy(p => p.Obsolete)
                        .ThenBy(p => p.Desc.Name.Length)
                        .Take(40)
                        .Select(p => new
                        {
                            name = p.Desc.Name,
                            nickname = p.Desc.NickName,
                            guid = p.Guid.ToString(),
                            obsolete = p.Obsolete,
                            category = p.Desc.Category,
                            subCategory = p.Desc.SubCategory
                        })
                        .ToList();

                    result = new { count = matches.Count, components = matches };
                }
                catch (Exception ex)
                {
                    exception = ex;
                }
            }));

            while (result == null && exception == null)
            {
                Thread.Sleep(10);
            }
            if (exception != null) { throw exception; }
            return result;
        }

        /// <summary>
        /// Toggles one of a component's variable input parameters — the entries that Robot Components
        /// and similar plugins expose only through their right-click menu (e.g. Move → Override Work
        /// Object). Calls the component's private AddParameter(int) via reflection.
        /// </summary>
        public static object AddVariableParameter(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            int index = command.GetParameter<int>("index");

            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                if (obj == null)
                {
                    throw new ArgumentException($"Component with ID {idStr} not found");
                }

                // Robot Components hides some parameters behind the right-click menu.
                // Inputs go through AddParameter(int), outputs through
                // AddOutputParameter(int) — e.g. Forward Kinematics → Posed Meshes.
                string side = command.GetParameter<string>("side");
                // Robot Components is not consistent: Move uses AddParameter, Forward
                // Kinematics AddOutputParameter, the RAPID Generator AddInputParameter.
                var candidates = string.Equals(side, "output", StringComparison.OrdinalIgnoreCase)
                    ? new[] { "AddOutputParameter", "AddParameter" }
                    : new[] { "AddParameter", "AddInputParameter" };
                string name = candidates.FirstOrDefault(candidate =>
                    obj.GetType().GetMethod(candidate,
                        System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance,
                        null, new[] { typeof(int) }, null) != null) ?? candidates[0];

                var method = obj.GetType().GetMethod(name,
                    System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance,
                    null, new[] { typeof(int) }, null);
                if (method == null)
                {
                    throw new ArgumentException($"{obj.GetType().Name} has no {name}(int) method");
                }

                method.Invoke(obj, new object[] { index });
                doc.NewSolution(false);

                var component = obj as IGH_Component;
                return new
                {
                    id = idStr,
                    index,
                    inputs = component?.Params.Input.Select(p => p.Name).ToList() ?? new List<string>(),
                    outputs = component?.Params.Output.Select(p => p.Name).ToList() ?? new List<string>()
                };
            });
        }

        /// <summary>
        /// Deletes a single component by instance id. The MCP bridge component itself is protected.
        /// </summary>
        public static object DeleteComponent(Command command)
        {
            string idStr = command.GetParameter<string>("id");
            if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
            {
                throw new ArgumentException("Valid component id is required");
            }

            return RunOnUiThread(doc =>
            {
                var obj = doc.FindObject(id, true);
                if (obj == null)
                {
                    throw new ArgumentException($"Component with ID {idStr} not found");
                }
                // Nur die echte Bruecken-KOMPONENTE schuetzen. Der fruehere
                // Namenstest traf auch Gruppen wie "MCP bridge (keep)" — die liessen
                // sich nie loeschen und sammelten sich bei jedem Umgruppieren an.
                if (obj is GrasshopperMCPComponent)
                {
                    throw new InvalidOperationException("Refusing to delete the MCP bridge component");
                }

                var removedType = obj.GetType().Name;
                doc.RemoveObject(obj, false);
                doc.NewSolution(false);

                return new { removed = idStr, type = removedType };
            });
        }
    }
}
