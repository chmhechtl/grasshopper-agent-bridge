using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using GrasshopperMCP.Models;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Special;
using Rhino;

namespace GrasshopperMCP.Commands
{
    /// <summary>
    /// Commands that describe a definition completely enough to understand or rebuild it —
    /// including the inside of clusters — and that manage several open documents.
    /// </summary>
    public static class StructureCommandHandler
    {
        private const int MaxPersistentItems = 20;

        // Unlike the inspection helper this does not require an active document:
        // new_document must work on an empty editor.
        private static object RunOnUi(Func<object> action)
        {
            object result = null;
            Exception exception = null;
            var done = new ManualResetEventSlim(false);

            RhinoApp.InvokeOnUiThread(new Action(() =>
            {
                try { result = action(); }
                catch (Exception ex) { exception = ex; }
                finally { done.Set(); }
            }));

            done.Wait();
            if (exception != null) { throw exception; }
            return result;
        }

        private static GH_Document ActiveDocument()
        {
            var doc = Grasshopper.Instances.ActiveCanvas?.Document;
            if (doc == null) { throw new InvalidOperationException("No active Grasshopper document"); }
            return doc;
        }

        private static GH_Cluster FindCluster(GH_Document doc, Guid id, int depth)
        {
            foreach (var obj in doc.Objects)
            {
                if (!(obj is GH_Cluster cluster)) { continue; }
                if (cluster.InstanceGuid == id) { return cluster; }
                if (depth >= 8) { continue; }
                var inner = cluster.Document("");
                var nested = inner == null ? null : FindCluster(inner, id, depth + 1);
                if (nested != null) { return nested; }
            }
            return null;
        }

        private static object DescribeParam(IGH_Param param)
        {
            // Values typed or internalised into the parameter: the part of a definition
            // that no wire shows.
            var persistent = new List<string>();
            int persistentCount = 0;
            if (param.GetType().GetProperty("PersistentData")?.GetValue(param) is IGH_Structure data)
            {
                persistentCount = data.DataCount;
                foreach (var goo in data.AllData(true))
                {
                    if (persistent.Count >= MaxPersistentItems) { break; }
                    persistent.Add(goo?.ToString() ?? "<null>");
                }
            }

            string expression = null;
            var expressionProperty = param.GetType().GetProperty("Expression");
            if (expressionProperty != null && expressionProperty.PropertyType == typeof(string))
            {
                expression = expressionProperty.GetValue(param) as string;
            }

            var sources = new List<object>();
            foreach (var source in param.Sources)
            {
                var owner = source.Attributes?.GetTopLevel?.DocObject ?? source;
                sources.Add(new
                {
                    id = owner.InstanceGuid.ToString(),
                    name = owner.NickName,
                    param = source.Name,
                    paramIndex = owner is IGH_Component component ? component.Params.Output.IndexOf(source) : 0
                });
            }

            return new
            {
                name = param.Name,
                nickname = param.NickName,
                dataType = param.TypeName,
                mapping = param.DataMapping.ToString(),   // None, Flatten or Graft
                reverse = param.Reverse,
                simplify = param.Simplify,
                expression,
                persistentCount,
                persistent,
                sources
            };
        }

        private static string ValueOf(IGH_DocumentObject obj)
        {
            if (obj is GH_Panel panel) { return panel.UserText; }
            if (obj is GH_NumberSlider slider)
            {
                return $"{slider.Slider.Minimum} < {slider.CurrentValue} < {slider.Slider.Maximum}";
            }
            if (obj is GH_BooleanToggle toggle) { return toggle.Value.ToString(); }
            if (obj is GH_ValueList list)
            {
                return string.Join(" | ", list.ListItems.Select(i => (i.Selected ? "*" : "") + i.Name + "=" + i.Expression));
            }
            if (obj is IGH_Param) { return null; }   // described by DescribeParam

            // Script source, expression text, scribble text, multi-dimensional sliders:
            // no common interface, but conventional property names.
            foreach (var name in new[] { "Expression", "Code", "ScriptSource", "Text", "Value" })
            {
                try
                {
                    var property = obj.GetType().GetProperty(name);
                    var value = property?.GetIndexParameters().Length == 0 ? property.GetValue(obj) : null;
                    if (value != null) { return value.ToString(); }
                }
                catch { /* a property that throws tells us nothing */ }
            }
            return null;
        }

        private static object DescribeObject(IGH_DocumentObject obj)
        {
            var inputs = new List<object>();
            var outputs = new List<object>();
            if (obj is IGH_Component component)
            {
                inputs.AddRange(component.Params.Input.Select(DescribeParam));
                outputs.AddRange(component.Params.Output.Select(DescribeParam));
            }
            else if (obj is IGH_Param param)
            {
                inputs.Add(DescribeParam(param));
            }

            return new
            {
                id = obj.InstanceGuid.ToString(),
                componentGuid = obj.ComponentGuid.ToString(),   // pass to add_component
                type = obj.GetType().Name,
                name = obj.Name,
                nickname = obj.NickName,
                x = obj.Attributes != null ? obj.Attributes.Pivot.X : 0f,
                y = obj.Attributes != null ? obj.Attributes.Pivot.Y : 0f,
                isCluster = obj is GH_Cluster,
                enabled = !(obj is IGH_ActiveObject active) || !active.Locked,
                value = ValueOf(obj),
                members = obj is GH_Group group ? group.ObjectIDs.Select(g => g.ToString()).ToList() : null,
                inputs,
                outputs
            };
        }

        /// <summary>
        /// Everything needed to understand or rebuild a definition: per object its component
        /// GUID, value, and for every parameter the data mapping, expression, internal values
        /// and sources. With 'clusterId' the inside of that cluster (nested ones included).
        /// </summary>
        public static object DescribeDocument(Command command)
        {
            string clusterIdStr = command.GetParameter<string>("clusterId");
            Guid clusterId = Guid.Empty;
            if (!string.IsNullOrEmpty(clusterIdStr) && !Guid.TryParse(clusterIdStr, out clusterId))
            {
                throw new ArgumentException("clusterId is not a valid id");
            }

            return RunOnUi(() =>
            {
                var doc = ActiveDocument();
                string scope = doc.DisplayName;
                if (clusterId != Guid.Empty)
                {
                    var cluster = FindCluster(doc, clusterId, 0);
                    if (cluster == null) { throw new ArgumentException($"No cluster with ID {clusterIdStr}"); }
                    doc = cluster.Document("");
                    if (doc == null) { throw new InvalidOperationException("The cluster is password protected"); }
                    scope = cluster.NickName;
                }

                var objects = doc.Objects.Select(DescribeObject).ToList();
                return new { scope, objectCount = objects.Count, objects };
            });
        }

        /// <summary>
        /// All documents open in the editor.
        /// </summary>
        public static object GetDocuments(Command command)
        {
            return RunOnUi(() =>
            {
                var active = Grasshopper.Instances.ActiveCanvas?.Document;
                var documents = new List<object>();
                int index = 0;
                foreach (GH_Document doc in Grasshopper.Instances.DocumentServer)
                {
                    documents.Add(new
                    {
                        index = index++,
                        name = doc.DisplayName,
                        path = doc.FilePath,
                        objectCount = doc.ObjectCount,
                        modified = doc.IsModified,
                        active = ReferenceEquals(doc, active)
                    });
                }
                return new { count = documents.Count, documents };
            });
        }

        /// <summary>
        /// Opens an empty document next to the ones already open and makes it active.
        /// Nothing is closed.
        /// </summary>
        public static object NewDocument(Command command)
        {
            return RunOnUi(() =>
            {
                var canvas = Grasshopper.Instances.ActiveCanvas;
                if (canvas == null) { throw new InvalidOperationException("The Grasshopper editor is not open"); }

                var doc = new GH_Document();
                Grasshopper.Instances.DocumentServer.AddDocument(doc);
                canvas.Document = doc;
                canvas.Refresh();
                return new { name = doc.DisplayName, documents = Grasshopper.Instances.DocumentServer.DocumentCount };
            });
        }

        /// <summary>
        /// Makes another open document the active one — by 'index' from get_documents, or by 'name'.
        /// </summary>
        public static object ActivateDocument(Command command)
        {
            string name = command.GetParameter<string>("name");
            bool hasIndex = command.Parameters.ContainsKey("index");
            int index = hasIndex ? command.GetParameter<int>("index") : -1;
            if (!hasIndex && string.IsNullOrEmpty(name))
            {
                throw new ArgumentException("Parameter 'index' or 'name' is required");
            }

            return RunOnUi(() =>
            {
                var canvas = Grasshopper.Instances.ActiveCanvas;
                if (canvas == null) { throw new InvalidOperationException("The Grasshopper editor is not open"); }

                var documents = Grasshopper.Instances.DocumentServer.Cast<GH_Document>().ToList();
                GH_Document target = hasIndex
                    ? (index >= 0 && index < documents.Count ? documents[index] : null)
                    : documents.FirstOrDefault(d => string.Equals(d.DisplayName.TrimEnd('*'), name.TrimEnd('*'), StringComparison.OrdinalIgnoreCase));
                if (target == null)
                {
                    throw new ArgumentException("No such document. Open: " + string.Join(", ", documents.Select(d => d.DisplayName)));
                }

                canvas.Document = target;
                canvas.Refresh();
                return new { name = target.DisplayName, path = target.FilePath, objectCount = target.ObjectCount };
            });
        }
    }
}
